// P010 / BT.2020 PQ preview. Resample the encoded RGB, then reproduce the
// existing zscale (100 nit reference) / Hable / display-referred Rec.709 path.
Texture2D<float> luma : register(t0);
Texture2D<float2> chroma : register(t1);
RWStructuredBuffer<float4> output_pixels : register(u0);
cbuffer Picture : register(b0) { uint sw; uint sh; uint dw; uint dh; };

float2 uv_at(int2 p) {
    return chroma.Load(int3(clamp(p, int2(0,0), int2((sw+1)/2-1,(sh+1)/2-1)),0));
}
float3 encoded_rgb(int x, int y) {
    x = clamp(x, 0, int(sw)-1); y = clamp(y, 0, int(sh)-1);
    float2 at = float2(x*0.5, (y-0.5)*0.5);
    int2 p = int2(floor(at)); float2 t = frac(at);
    float2 uv = lerp(lerp(uv_at(p), uv_at(p+int2(1,0)), t.x),
                     lerp(uv_at(p+int2(0,1)), uv_at(p+int2(1,1)), t.x), t.y);
    float Y = (luma.Load(int3(x,y,0))*1023.984375-64.0)/876.0;
    uv = (uv*1023.984375-512.0)/896.0;
    return float3(Y+1.4746*uv.y, Y-0.16455312684366*uv.x-0.57135312684366*uv.y, Y+1.8814*uv.x);
}
float3 linear_pq(float3 rgb) {
    float3 p = pow(max(rgb, 0.0), 1.0/78.84375);
    // YUV range excursions can cross PQ's asymptote. Keep its limiting white
    // finite so the subsequent RGB/desaturation math cannot turn it black.
    float3 denominator = max(18.8515625-18.6875*p, 1e-6);
    return 100.0 * pow(max(p-0.8359375,0.0)/denominator, 1.0/0.1593017578125);
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
    float2 scale = float2(sw,sh)/float2(dw,dh);
    float2 center = (float2(id.xy)+0.5)*scale-0.5;
    float2 radius = max(scale,1.0);
    int2 first = int2(ceil(center-radius)); int2 last = int2(floor(center+radius));
    float3 rgb = 0.0; float weight = 0.0;
    for (int y=first.y; y<=last.y; ++y) {
        float wy = max(1.0-abs(y-center.y)/radius.y,0.0);
        for (int x=first.x; x<=last.x; ++x) {
            float w = wy*max(1.0-abs(x-center.x)/radius.x,0.0);
            rgb += w*encoded_rgb(x,y); weight += w;
        }
    }
    rgb = linear_pq(rgb/weight);
    rgb = mul(float3x3(1.6604910021,-0.5876411388,-0.0728498633,
                       -0.1245504745,1.1328998971,-0.0083494226,
                       -0.0181507634,-0.1005788980,1.1187296614),rgb);
    // zscale removes the original HDR metadata when changing the transfer;
    // FFmpeg's linear-frame fallback is a peak of 10, with RGB luma coefficients.
    float L = rgb.r+rgb.g+rgb.b;
    float over = max(L-2.0,1e-6)/max(L,1e-6);
    rgb = lerp(rgb,L.xxx,over);
    float signal = max(max(rgb.r,max(rgb.g,rgb.b)),1e-6);
    rgb *= hable(signal)/(hable(10.0)*signal);
    rgb = pow(max(rgb,0.0),1.0/2.4);
    output_pixels[id.y*dw+id.x] = float4(round(saturate(rgb)*65535.0)/65535.0,1.0);
}
