"""Experimental GLSL adaptation of XeGTAO's horizon integral.

Full-resolution fragment passes, exact acos, fixed spatial noise, inverse projection
for orthographic support. Uses full-res depth (no depth MIPs yet), and our own
depth-aware 5x5 spatial filter. Not the complete upstream compute implementation.
Horizon integration adapted from https://github.com/GameTechDev/XeGTAO
Copyright (C) 2016-2021, Intel Corporation. MIT: ../licenses/XeGTAO.txt.
"""
import gpu
from .ssao import SSAO
from .effect import FS_VERT

AO = '''
uniform sampler2D uDepth, uAoDepth;
uniform mat4 uProj, uInvProj;
uniform float uRadius, uBias, uRidge;
uniform int uSamples;
in vec2 vUV;
out vec4 fragColor;
const float PI=3.14159265359;
vec3 pos(vec2 uv,float d){vec4 p=uInvProj*vec4(uv*2.0-1.0,d*2.0-1.0,1);return p.xyz/p.w;}
ivec2 bounded(ivec2 p){return clamp(p,ivec2(0),textureSize(uDepth,0)-1);}
vec3 at(ivec2 p){p=bounded(p);return pos((vec2(p)+.5)/vec2(textureSize(uDepth,0)),texelFetch(uDepth,p,0).r);}
void main(){
 ivec2 pixel=ivec2(gl_FragCoord.xy);vec2 size=vec2(textureSize(uDepth,0));
 float z=texelFetch(uDepth,pixel,0).r;
 if(z>=1.0){fragColor=vec4(0,0,0,0);return;}
 vec3 P=pos(vUV,z);
 float az=texelFetch(uAoDepth,pixel,0).r;
 if(z<az-0.0008){fragColor=vec4(0,0,P.z,0);return;}
 vec3 left=P-at(pixel-ivec2(1,0)),right=at(pixel+ivec2(1,0))-P;
 vec3 down=P-at(pixel-ivec2(0,1)),up=at(pixel+ivec2(0,1))-P;
 vec3 dx=abs(left.z)<abs(right.z)?left:right,dy=abs(down.z)<abs(up.z)?down:up;
 vec3 V=abs(uProj[3][3])>.5?vec3(0,0,1):normalize(-P);
 vec3 N=cross(dx,dy);N=dot(N,N)>1e-20?normalize(N):V;if(dot(N,V)<0)N=-N;
 float pixelWorld=length(pos(vUV+vec2(1.0/size.x,0),z)-P);
 float radiusPixels=uRadius/max(pixelWorld,1e-8);
 int slices=uSamples<=16?2:(uSamples<=32?3:4);
 int steps=max(2,uSamples/(slices*2));
 float noise=fract(52.9829189*fract(dot(vec2(pixel),vec2(.06711056,.00583715))));
 float visibility=0.0,ridge=0.0;
 for(int slice=0;slice<4;slice++){
  if(slice>=slices)break;
  float phi=(float(slice)+noise)/float(slices)*PI;
  vec2 direction=vec2(cos(phi),sin(phi));
  vec3 D=vec3(direction,0),ortho=D-dot(D,V)*V;
  vec3 axis=normalize(cross(ortho,V));
  vec3 projected=N-axis*dot(N,axis);float plen=length(projected);
  if(plen<1e-5)continue;
  float cn=clamp(dot(projected,V)/plen,0.0,1.0);
  float n=sign(dot(ortho,projected))*acos(cn);
  vec2 low=cos(vec2(n+PI*.5,n-PI*.5)),horizon=low;
  for(int step=0;step<8;step++){
   if(step>=steps)break;
   float jitter=fract(noise+(float(slice+step*steps))*.61803398875);
   float s=(float(step)+jitter)/float(steps);s=s*s;
   vec2 delta=round(direction*(s*radiusPixels+1.3));
   for(int side=0;side<2;side++){
    vec2 uv=vUV+delta*(side==0?1.0:-1.0)/size;
    if(any(lessThan(uv,vec2(0)))||any(greaterThanEqual(uv,vec2(1))))continue;
    float sampleZ=texelFetch(uAoDepth,ivec2(uv*size),0).r;if(sampleZ>=1.0)continue;
    vec3 diff=pos(uv,sampleZ)-P;float dist=length(diff);if(dist<1e-6)continue;
    // Reject samples below the tangent plane using the world-space bias.
    float above=dot(diff,N);float biasWeight=smoothstep(0.0,max(uBias,1e-6),above);
    float falloff=clamp((uRadius-dist)/(uRadius*.615),0.0,1.0)*biasWeight;
    horizon[side]=max(horizon[side],mix(low[side],dot(diff/dist,V),falloff));
    if(uRidge>0.0)ridge+=max(-above/dist-uBias,0.0)*clamp(1.0-dist/uRadius,0.0,1.0);
   }
  }
  float h0=-acos(clamp(horizon.y,-1.0,1.0)),h1=acos(clamp(horizon.x,-1.0,1.0));
  float a0=(cn+2.0*h0*sin(n)-cos(2.0*h0-n))*.25;
  float a1=(cn+2.0*h1*sin(n)-cos(2.0*h1-n))*.25;
  visibility+=mix(plen,1.0,.05)*(a0+a1);
 }
 float occlusion=1.0-clamp(visibility/float(slices),0.03,1.0);
 fragColor=vec4(occlusion,ridge/float(slices*steps*2),P.z,1);
}
'''

APPLY = '''
uniform sampler2D uColor,uAO,uAOMask;
uniform float uStrength,uRidge;
in vec2 vUV;out vec4 fragColor;
void main(){
 ivec2 p=ivec2(gl_FragCoord.xy),sz=textureSize(uAO,0);
 vec4 c=texture(uColor,vUV),center=texelFetch(uAO,p,0);
 if(center.a<.5){fragColor=c;return;}
 vec2 value=vec2(0);float weightSum=0;
 float threshold=max(.002,abs(center.z)*.002);
 for(int y=-2;y<=2;y++)for(int x=-2;x<=2;x++){
  ivec2 q=p+ivec2(x,y);if(any(lessThan(q,ivec2(0)))||any(greaterThanEqual(q,sz)))continue;
  vec4 a=texelFetch(uAO,q,0);if(a.a<.5)continue;
  float w=exp(-float(x*x+y*y)*.35)*exp(-abs(a.z-center.z)/threshold);
  value+=a.xy*w;weightSum+=w;
 }
 value/=max(weightSum,1e-8);
 float amount=texture(uAOMask,vUV).a;
 fragColor=vec4(c.rgb*mix(1.0,clamp(1.0-value.x*uStrength,0.0,1.0),amount)*(1.0+value.y*uRidge*amount),c.a);
}
'''

class GTAO(SSAO):
    name='gtao'
    frag=APPLY
    def enabled(self,vls):
        return bool(getattr(vls,'use_ao',False)) and getattr(vls,'ao_method','SSAO')=='GTAO'
    def _ao_shader(self):
        if self._ao_sh is None:
            from gpu_extras.batch import batch_for_shader
            self._ao_sh=gpu.types.GPUShader(FS_VERT,AO)
            self._ao_batch=batch_for_shader(self._ao_sh,'TRIS',{'pos':[(-1,-1),(3,-1),(-1,3)]})
        return self._ao_sh
