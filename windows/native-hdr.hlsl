// Numerical compatibility of zimg AVX512 approximations.
// Coefficients: zimg 75ad930ee74f9c2aaf96bbbc0810f5fc1e42e698,
// https://github.com/sekrit-twc/zimg/blob/75ad930ee74f9c2aaf96bbbc0810f5fc1e42e698/src/zimg/colorspace/x86/gamma_constants_avx512.cpp
// Licensed under WTFPL version 2; see native-hdr-zimg.COPYING and native-hdr-zimg-provenance.json.
static const float Rec1886InverseEOTF_horner[6] = {
	5.3331316297790816e-3f,
	-5.0653335401261418e-2f,
	2.0631810268332693e-1f,
	-4.8846483066245743e-1f,
	9.5048057786988787e-1f,
	3.7698771958831039e-1f,
};
static const float Rec1886InverseEOTF_table[32] = {
	0.00000000e+00f, 
	1.72633492e-04f, 
	2.30438065e-04f, 
	3.07597913e-04f, 
	4.10593953e-04f, 
	5.48077172e-04f, 
	7.31595252e-04f, 
	9.76562500e-04f, 
	1.30355455e-03f, 
	1.74003656e-03f, 
	2.32267015e-03f, 
	3.10039268e-03f, 
	4.13852771e-03f, 
	5.52427173e-03f, 
	7.37401807e-03f, 
	9.84313320e-03f, 
	1.31390065e-02f, 
	1.75384695e-02f, 
	2.34110481e-02f, 
	3.12500000e-02f, 
	4.17137454e-02f, 
	5.56811699e-02f, 
	7.43254447e-02f, 
	9.92125657e-02f, 
	1.32432887e-01f, 
	1.76776695e-01f, 
	2.35968578e-01f, 
	3.14980262e-01f, 
	4.20448208e-01f, 
	5.61231024e-01f, 
	7.49153538e-01f, 
	1.00000000e+00f, 
};
static const float ST2084EOTF_horner0[32] = {
	2.3783206e-1f, 5.3487723e-2f, 6.9725438e-2f, 9.2311500e-2f, 
	1.2176837e-1f, 1.6016700e-1f, 2.1029731e-1f, 2.7583897e-1f, 
	3.6165950e-1f, 4.7422258e-1f, 6.2214308e-1f, 8.1694541e-1f, 
	1.0741050e+0f, 1.4144856e+0f, 1.8663342e+0f, 2.4680621e+0f, 
	3.2721476e+0f, 4.3506393e+0f, 5.8029690e+0f, 7.7671092e+0f, 
	1.0435617e+1f, 1.4078866e+1f, 1.9078925e+1f, 2.5979369e+1f, 
	3.5559070e+1f, 4.8942502e+1f, 6.7766052e+1f, 9.4431226e+1f, 
	1.3249397e+2f, 1.8726969e+2f, 2.6678396e+2f, 3.8328445e+2f, 
};
static const float ST2084EOTF_horner1[32] = {
	-4.4913414e-3f, +1.0114087e-2f, +6.0346995e-3f, -2.4363002e-3f, 
	-1.7180403e-2f, -4.1212870e-2f, -7.8865726e-2f, -1.3629793e-1f, 
	-2.2223892e-1f, -3.4904270e-1f, -5.3418094e-1f, -8.0236306e-1f, 
	-1.1885557e+0f, -1.7422975e+0f, -2.5338891e+0f, -3.6633069e+0f, 
	-5.2731001e+0f, -7.5671345e+0f, -1.0837977e+1f, -1.5507119e+1f, 
	-2.2184402e+1f, -3.1756357e+1f, -4.5518394e+1f, -6.5373990e+1f, 
	-9.4137073e+1f, -1.3599470e+2f, -1.9722094e+2f, -2.8728825e+2f, 
	-4.2061406e+2f, -6.1933324e+2f, -9.1774668e+2f, -1.3695407e+3f, 
};
static const float ST2084EOTF_horner2[32] = {
	2.0212520e-3f, 1.6286117e-3f, 2.0177877e-3f, 3.2161629e-3f, 
	5.9926554e-3f, 1.1644820e-2f, 2.2265499e-2f, 4.1157759e-2f, 
	7.3456985e-2f, 1.2705851e-1f, 2.1399855e-1f, 3.5250895e-1f, 
	5.7007568e-1f, 9.0799574e-1f, 1.4281776e+0f, 2.2233112e+0f, 
	3.4321180e+0f, 5.2622903e+0f, 8.0251232e+0f, 1.2188015e+1f, 
	1.8454418e+1f, 2.7886218e+1f, 4.2092088e+1f, 6.3519144e+1f, 
	9.5907509e+1f, 1.4500381e+2f, 2.1968960e+2f, 3.3378077e+2f, 
	5.0892188e+2f, 7.7928620e+2f, 1.1992847e+3f, 1.8563487e+3f, 
};
static const float ST2084EOTF_horner3[32] = {
	+2.8802992e-6f, +6.7830084e-6f, -9.9130278e-6f, -8.5689092e-5f, 
	-3.1881062e-4f, -9.1083514e-4f, -2.2441828e-3f, -5.0091196e-3f, 
	-1.0408578e-2f, -2.0485210e-2f, -3.8639718e-2f, -7.0447779e-2f, 
	-1.2494241e-1f, -2.1662153e-1f, -3.6858557e-1f, -6.1743835e-1f, 
	-1.0209430e+0f, -1.6699941e+0f, -2.7073699e+0f, -4.3571745e+0f, 
	-6.9712028e+0f, -1.1102217e+1f, -1.7620252e+1f, -2.7898091e+1f, 
	-4.4108683e+1f, -6.9704922e+1f, -1.1019876e+2f, -1.7443571e+2f, 
	-2.7669622e+2f, -4.4019065e+2f, -7.0292656e+2f, -1.1276591e+3f, 
};
static const float ST2084EOTF_horner4[32] = {
	-5.0238915e-10f, -9.0804149e-9f, 2.6239238e-7f, 2.0689909e-6f, 
	9.4319669e-6f, 3.2732739e-5f, 9.5593041e-5f, 2.4749664e-4f, 
	5.8625125e-4f, 1.2970695e-3f, 2.7194061e-3f, 5.4597617e-3f, 
	1.0580125e-2f, 1.9910299e-2f, 3.6562491e-2f, 6.5775423e-2f, 
	1.1629487e-1f, 2.0262735e-1f, 3.4871640e-1f, 5.9394040e-1f, 
	1.0029083e+0f, 1.6814878e+0f, 2.8031002e+0f, 4.6520049e+0f, 
	7.6948422e+0f, 1.2699455e+1f, 2.0933328e+1f, 3.4497073e+1f, 
	5.6888793e+1f, 9.3966622e+1f, 1.5560442e+2f, 2.5856660e+2f, 
};
// P010 / BT.2020 PQ preview. Resample the encoded RGB, then reproduce the
// existing zscale (100 nit reference) / Hable / display-referred Rec.709 path.
Texture2D<float> luma : register(t0);
Texture2D<float2> chroma : register(t1);
RWStructuredBuffer<uint2> output_pixels : register(u0);
cbuffer Picture : register(b0) { uint sw; uint sh; uint dw; uint dh; };

float2 uv_at(int2 p) {
    return chroma.Load(int3(clamp(p, int2(0,0), int2((sw+1)/2-1,(sh+1)/2-1)),0));
}
float3 encoded_rgb(int x, int y) {
    x = clamp(x, 0, int(sw)-1); y = clamp(y, 0, int(sh)-1);
    float2 at = float2(x*0.5, (y-0.5)*0.5);
    int2 p = int2(floor(at)); float2 t = frac(at);
    // Native zimg 10-bit chroma reconstruction quantizes each separable pass.
    float2 a = round(uv_at(p)*1023.984375);
    float2 b = round(uv_at(p+int2(1,0))*1023.984375);
    float2 c = round(uv_at(p+int2(0,1))*1023.984375);
    float2 d = round(uv_at(p+int2(1,1))*1023.984375);
    float2 h0 = floor(lerp(a,b,t.x)+0.5);
    float2 h1 = floor(lerp(c,d,t.x)+0.5);
    float2 uv = floor(lerp(h0,h1,t.y)+0.5);
    float Y = (luma.Load(int3(x,y,0))*1023.984375-64.0)/876.0;
    uv = (uv-512.0)/896.0;
    return float3(mad(1.4746,uv.y,Y),mad(-0.57135312684366,uv.y,mad(-0.16455312684366,uv.x,Y)),mad(1.8814,uv.x,Y));
}
float linear_pq_scalar(float x) {
    x=max(x,1.17549435e-38);
    uint i=(uint)(min(x,.999999940)*32.0);
    float q=ST2084EOTF_horner0[i];
    q=mad(q,x,ST2084EOTF_horner1[i]);
    q=mad(q,x,ST2084EOTF_horner2[i]);
    q=mad(q,x,ST2084EOTF_horner3[i]);
    q=mad(q,x,ST2084EOTF_horner4[i]);
    return max(q,0.0)*100.0;
}
float3 linear_pq(float3 rgb) { return float3(linear_pq_scalar(rgb.r),linear_pq_scalar(rgb.g),linear_pq_scalar(rgb.b)); }
float gamma_scalar(float x){
    x=max(x,0.0);float base=min(x,1.99999988);
    uint bits=asuint(base);float mant=asfloat((bits&0x7fffff)|0x3f800000);
    uint e=max(bits>>23,96u);
    float q=Rec1886InverseEOTF_horner[0];
    for(int i=1;i<6;i++)q=mad(q,mant,Rec1886InverseEOTF_horner[i]);
    return q*Rec1886InverseEOTF_table[e&31];
}
float hable(float x) {
    // Divide by x squared at high luminance: the original float products
    // overflow on extended-range PQ even though the rational limit is finite.
    if (x>1.0) {
        float inv=1.0/x;
        return (0.15+0.05*inv+0.004*inv*inv)/(0.15+0.50*inv+0.06*inv*inv)-0.02/0.30;
    }
    return (x*(x*0.15+0.05)+0.004)/(x*(x*0.15+0.50)+0.06)-0.02/0.30;
}
[numthreads(16,16,1)]
void main(uint3 id : SV_DispatchThreadID) {
    if (id.x>=dw || id.y>=dh) return;
    float3 rgb = linear_pq(encoded_rgb(id.x,id.y));
    rgb = float3(mad(-0.0728498633,rgb.b,mad(-0.5876411388,rgb.g,1.6604910021*rgb.r)),
                 mad(-0.0083494226,rgb.b,mad(1.1328998971,rgb.g,-0.1245504745*rgb.r)),
                 mad(1.1187296614,rgb.b,mad(-0.1005788980,rgb.g,-0.0181507634*rgb.r)));
    // zscale removes the original HDR metadata when changing the transfer;
    // FFmpeg's linear-frame fallback is a peak of 10, with RGB luma coefficients.
    float L = rgb.r+rgb.g+rgb.b;
    float over = max(L-2.0,1e-6)/max(L,1e-6);
    rgb = lerp(rgb,L.xxx,over);
    float signal = max(max(rgb.r,max(rgb.g,rgb.b)),1e-6);
    rgb *= hable(signal)/(hable(10.0)*signal);
    rgb=float3(gamma_scalar(rgb.r),gamma_scalar(rgb.g),gamma_scalar(rgb.b));
    if (!all(isfinite(rgb))) { InterlockedOr(output_pixels[dw*dh].x,1); return; }
    uint3 code = (uint3)round(saturate(rgb)*65535.0);
    output_pixels[id.y*dw+id.x] = uint2(code.r | (code.g<<16),code.b | (65535u<<16));
}
