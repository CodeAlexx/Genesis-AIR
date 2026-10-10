// Selected-frame D3D11 compute preview; master rendering retains its color graph.
#define COBJMACROS
#include <libavutil/hwcontext.h>
#include <libavutil/hwcontext_d3d11va.h>
#include <libavutil/frame.h>
#include <libavutil/time.h>
#include <d3dcompiler.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
int fpx_gpu_external_reserve(uint64_t);
void fpx_gpu_external_release(uint64_t);
uint64_t fpx_gpu_external_bytes(void);
#include <string.h>
#include <windows.h>
#include "genesis-native-hdr-shader.h"

typedef struct {
    AVBufferRef *frames;
    AVHWFramesContext *hardware;
    AVD3D11VADeviceContext *device;
    ID3D11ComputeShader *shader;
    ID3D11Texture2D *input;
    ID3D11ShaderResourceView *y, *uv;
    ID3D11Buffer *pixels, *readback, *constants;
    ID3D11UnorderedAccessView *output;
    unsigned width, height, dw, dh;
    HMODULE compiler;
    uint64_t reserved; uint16_t *host;
} GenesisNativeHdr;

#define RELEASE(value) do { if (value) IUnknown_Release((IUnknown*)(value)); value = NULL; } while(0)
void genesis_nativehdr_close(void **handle) {
    GenesisNativeHdr *p = *handle;
    if (!p) return;
    RELEASE(p->output); RELEASE(p->y); RELEASE(p->uv);
    RELEASE(p->pixels); RELEASE(p->readback); RELEASE(p->constants);
    RELEASE(p->input); RELEASE(p->shader);
    if (p->compiler) FreeLibrary(p->compiler);
    av_buffer_unref(&p->frames); free(p->host);
    if(p->reserved) fpx_gpu_external_release(p->reserved);
    if(getenv("GENESIS_NATIVE_COLOR_PROFILE"))fprintf(stderr,"NATIVEHDR_CLOSE external_bytes=%llu\n",(unsigned long long)fpx_gpu_external_bytes());
    free(p); *handle = NULL;
}

static int create(GenesisNativeHdr *p, const AVFrame *frame, int dw, int dh) {
    if(dw!=frame->width || dh!=frame->height || dw<2 || dh<2 || dw>8192 || dh>8192 || (uint64_t)dw*dh>16777216)return -1;
    D3D11_TEXTURE2D_DESC source_desc;
    ID3D11Texture2D_GetDesc((ID3D11Texture2D*)frame->data[0], &source_desc);
    uint64_t reservation=(uint64_t)source_desc.Width*source_desc.Height*3+((uint64_t)dw*dh+1)*16+16;
    if(fpx_gpu_external_reserve(reservation)!=0)return -1;
    p->reserved=reservation;
    if(getenv("GENESIS_NATIVE_HDR_FAULT") && !strcmp(getenv("GENESIS_NATIVE_HDR_FAULT"),"reserve"))return -1;
    p->host=malloc((size_t)dw*dh*8);if(!p->host)return -1;
    p->frames = av_buffer_ref(frame->hw_frames_ctx);
    if (!p->frames) return -1;
    p->hardware = (AVHWFramesContext*)p->frames->data;
    p->device = (AVD3D11VADeviceContext*)p->hardware->device_ctx->hwctx;
    ID3D11Device *device = p->device->device;
    ID3DBlob *code = NULL, *errors = NULL;
    p->compiler = LoadLibraryExW(L"d3dcompiler_47.dll", NULL, LOAD_LIBRARY_SEARCH_SYSTEM32);
    typedef HRESULT (WINAPI *Compile)(LPCVOID,SIZE_T,LPCSTR,const D3D_SHADER_MACRO*,ID3DInclude*,LPCSTR,LPCSTR,UINT,UINT,ID3DBlob**,ID3DBlob**);
    Compile compile = p->compiler ? (Compile)GetProcAddress(p->compiler,"D3DCompile") : NULL;
    if (!compile) { fprintf(stderr,"[GA_GPU_COLOR] Windows shader compiler unavailable\n"); return -1; }
    HRESULT result = compile(genesis_native_hdr_shader, sizeof(genesis_native_hdr_shader)-1,
        "Genesis HDR preview", NULL, NULL, "main", "cs_5_0",
        D3DCOMPILE_OPTIMIZATION_LEVEL3 | D3DCOMPILE_IEEE_STRICTNESS, 0, &code, &errors);
    if (FAILED(result)) {
        fprintf(stderr, "[GA_GPU_COLOR] Shader compilation failed (0x%08lx): %.*s\n", result,
            errors ? (int)ID3D10Blob_GetBufferSize(errors) : 0, errors ? (char*)ID3D10Blob_GetBufferPointer(errors) : "");
        RELEASE(errors); RELEASE(code); return -1;
    }
    result = ID3D11Device_CreateComputeShader(device, ID3D10Blob_GetBufferPointer(code), ID3D10Blob_GetBufferSize(code), NULL, &p->shader);
    RELEASE(errors); RELEASE(code);
    if (FAILED(result)) return -1;
    D3D11_TEXTURE2D_DESC desc;
    ID3D11Texture2D_GetDesc((ID3D11Texture2D*)frame->data[0], &desc);
    desc.ArraySize = 1; desc.MipLevels = 1; desc.Usage = D3D11_USAGE_DEFAULT;
    desc.BindFlags = D3D11_BIND_SHADER_RESOURCE; desc.CPUAccessFlags = 0; desc.MiscFlags = 0;
    if (desc.Format != DXGI_FORMAT_P010 || FAILED(ID3D11Device_CreateTexture2D(device, &desc, NULL, &p->input))) return -1;
    D3D11_SHADER_RESOURCE_VIEW_DESC view = {0};
    view.Format = DXGI_FORMAT_R16_UNORM; view.ViewDimension = D3D11_SRV_DIMENSION_TEXTURE2D;
    view.Texture2D.MipLevels = 1;
    if (FAILED(ID3D11Device_CreateShaderResourceView(device, (ID3D11Resource*)p->input, &view, &p->y))) return -1;
    view.Format = DXGI_FORMAT_R16G16_UNORM;
    if (FAILED(ID3D11Device_CreateShaderResourceView(device, (ID3D11Resource*)p->input, &view, &p->uv))) return -1;
    D3D11_BUFFER_DESC buffer = {0};
    buffer.ByteWidth = (UINT)(((size_t)dw*dh+1)*8); buffer.BindFlags = D3D11_BIND_UNORDERED_ACCESS;
    buffer.MiscFlags = D3D11_RESOURCE_MISC_BUFFER_STRUCTURED; buffer.StructureByteStride = 8;
    if (FAILED(ID3D11Device_CreateBuffer(device, &buffer, NULL, &p->pixels))) return -1;
    D3D11_UNORDERED_ACCESS_VIEW_DESC output = {0};
    output.ViewDimension = D3D11_UAV_DIMENSION_BUFFER; output.Buffer.NumElements = (UINT)((size_t)dw*dh+1);
    if (FAILED(ID3D11Device_CreateUnorderedAccessView(device, (ID3D11Resource*)p->pixels, &output, &p->output))) return -1;
    buffer.BindFlags = 0; buffer.MiscFlags = 0; buffer.StructureByteStride = 0;
    buffer.Usage = D3D11_USAGE_STAGING; buffer.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
    if (FAILED(ID3D11Device_CreateBuffer(device, &buffer, NULL, &p->readback))) return -1;
    buffer.ByteWidth = 16; buffer.BindFlags = D3D11_BIND_CONSTANT_BUFFER; buffer.Usage = D3D11_USAGE_DEFAULT; buffer.CPUAccessFlags = 0;
    unsigned dimensions[4] = {frame->width, frame->height, dw, dh};
    D3D11_SUBRESOURCE_DATA data = {dimensions, 0, 0};
    if (FAILED(ID3D11Device_CreateBuffer(device, &buffer, &data, &p->constants))) return -1;
    if(getenv("GENESIS_NATIVE_HDR_FAULT") && !strcmp(getenv("GENESIS_NATIVE_HDR_FAULT"),"resources"))return -1;
    p->width = frame->width; p->height = frame->height; p->dw = dw; p->dh = dh;
    return 0;
}

int genesis_nativehdr_frame(void **handle, const AVFrame *frame, const uint16_t **out, int dw, int dh) {
    GenesisNativeHdr *p = *handle;
    if (p && (p->frames->data != frame->hw_frames_ctx->data || p->width != frame->width || p->height != frame->height || p->dw != dw || p->dh != dh)) {
        genesis_nativehdr_close(handle); p = NULL;
    }
    if (!p) {
        p = calloc(1, sizeof(*p));
        if (!p) return -1;
        *handle = p;
        if (create(p, frame, dw, dh) < 0) { genesis_nativehdr_close(handle); return -1; }
        fprintf(stderr, "[gcompose] Native HDR: %ux%u -> %ux%u RGBA16\n", p->width,p->height,p->dw,p->dh);
    }
    int64_t started = av_gettime_relative();
    AVD3D11VADeviceContext *device = p->device;
    ID3D11DeviceContext *context = device->device_context;
    if (device->lock) device->lock(device->lock_ctx);
    ID3D11DeviceContext_CopySubresourceRegion(context, (ID3D11Resource*)p->input,0,0,0,0,
        (ID3D11Resource*)frame->data[0], (UINT)(uintptr_t)frame->data[1], NULL);
    int64_t copy_submitted=av_gettime_relative();
    ID3D11ShaderResourceView *views[2] = {p->y,p->uv};
    const UINT clear[4]={0,0,0,0};
    ID3D11DeviceContext_ClearUnorderedAccessViewUint(context,p->output,clear);
    ID3D11DeviceContext_CSSetShader(context,p->shader,NULL,0);
    ID3D11DeviceContext_CSSetShaderResources(context,0,2,views);
    ID3D11DeviceContext_CSSetUnorderedAccessViews(context,0,1,&p->output,NULL);
    ID3D11DeviceContext_CSSetConstantBuffers(context,0,1,&p->constants);
    ID3D11DeviceContext_Dispatch(context,(dw+15)/16,(dh+15)/16,1);
    int64_t dispatch_submitted=av_gettime_relative();
    ID3D11ShaderResourceView *empty_views[2] = {NULL,NULL};
    ID3D11UnorderedAccessView *empty_output = NULL;
    ID3D11DeviceContext_CSSetShaderResources(context,0,2,empty_views);
    ID3D11DeviceContext_CSSetUnorderedAccessViews(context,0,1,&empty_output,NULL);
    ID3D11Buffer *empty_constants = NULL;
    ID3D11DeviceContext_CSSetConstantBuffers(context,0,1,&empty_constants);
    ID3D11DeviceContext_CSSetShader(context,NULL,NULL,0);
    ID3D11DeviceContext_CopyResource(context,(ID3D11Resource*)p->readback,(ID3D11Resource*)p->pixels);
    int64_t read_submitted=av_gettime_relative();
    D3D11_MAPPED_SUBRESOURCE mapped = {0};
    HRESULT result = ID3D11DeviceContext_Map(context,(ID3D11Resource*)p->readback,0,D3D11_MAP_READ,0,&mapped);
    int64_t map_ready=av_gettime_relative();
    if (SUCCEEDED(result)) {
        if(getenv("GENESIS_NATIVE_HDR_FAULT") && !strcmp(getenv("GENESIS_NATIVE_HDR_FAULT"),"map"))result=E_FAIL;
        if(((const uint32_t*)mapped.pData)[(size_t)dw*dh*2]) result=E_FAIL;
        else if(SUCCEEDED(result)) {memcpy(p->host,mapped.pData,(size_t)dw*dh*8);*out=p->host;}
        ID3D11DeviceContext_Unmap(context,(ID3D11Resource*)p->readback,0);
    }
    if (device->unlock) device->unlock(device->lock_ctx);
    if (getenv("GENESIS_NATIVE_COLOR_PROFILE")) fprintf(stderr,"NATIVEHDR gpu_color_us=%lld readback_bytes=%zu copy_submit_us=%lld dispatch_submit_us=%lld read_submit_us=%lld map_wait_us=%lld host_copy_us=%lld external_bytes=%llu\n",(long long)(av_gettime_relative()-started),(size_t)dw*dh*8,(long long)(copy_submitted-started),(long long)(dispatch_submitted-copy_submitted),(long long)(read_submitted-dispatch_submitted),(long long)(map_ready-read_submitted),(long long)(av_gettime_relative()-map_ready),(unsigned long long)fpx_gpu_external_bytes());
    return SUCCEEDED(result) ? 0 : -1;
}
