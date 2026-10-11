#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "air_rt.h"
#ifndef GENESIS_NET_SOURCE
#error GENESIS_NET_SOURCE must name the Windows AIR TCP provider
#endif
#include GENESIS_NET_SOURCE

static SOCKET native(const air_socket *s) {return (SOCKET)(uintptr_t)s->fd;}
static air_view probe_host={"127.0.0.1",9};
static int get(air_socket *s,int opt) {
    int value=-1,size=sizeof value;
    return getsockopt(native(s),SOL_SOCKET,opt,(char*)&value,&size)==0?value:-1;
}
static unsigned char expected(uint64_t at) {
    const uint64_t frame=65536u+96u;
    return (unsigned char)(((at%frame)*37u+(at/frame)*13u+71u)%256u);
}
static int pool(void) {
    air_socket senders[32],receivers[32],listeners[32];
    unsigned count=0;int ok=1;uint64_t room=0,drained=0;
    air_view host=probe_host;
    for(unsigned i=0;i<32;++i) {
        air_result_socket ls=air_net_tcp_listen(host,0,4);if(ls.tag!=AIR_TAG_OK){ok=0;break;}
        listeners[count]=ls.u.ok;
        air_result_port_net port=air_net_tcp_local_port(&listeners[count]);if(port.tag!=AIR_TAG_OK){air_net_tcp_close(listeners[count]);ok=0;break;}
        air_result_socket cs=air_net_tcp_connect(host,port.u.ok);if(cs.tag!=AIR_TAG_OK){air_net_tcp_close(listeners[count]);ok=0;break;}
        senders[count]=cs.u.ok;
        air_result_socket as=air_net_tcp_accept_until(&listeners[count],air_time_monotonic_ns()+2000000000ull);
        if(as.tag!=AIR_TAG_OK){air_net_tcp_close(senders[count]);air_net_tcp_close(listeners[count]);ok=0;break;}
        receivers[count]=as.u.ok;++count;
        int sb=get(&senders[i],SO_SNDBUF),rb=get(&receivers[i],SO_SNDBUF);
        if(sb!=1048576||rb!=1048576)ok=0;
        room+=(uint64_t)sb+(uint64_t)(rb>0?rb:0);
    }
    unsigned char payload[65536+96];
    for(unsigned i=0;i<count;++i)for(unsigned block=0;block<16;++block){
        for(unsigned j=0;j<sizeof payload;++j)payload[j]=expected((uint64_t)block*sizeof payload+j);
        air_view value={payload,sizeof payload};
        if(air_net_tcp_send_until(&senders[i],value,air_time_monotonic_ns()+2000000000ull).tag!=AIR_TAG_OK){ok=0;break;}
    }
    for(unsigned i=0;i<count;++i){
        uint64_t received=0;
        while(received<16u*sizeof payload){
            air_result_buf_net data=air_net_tcp_recv_until(&receivers[i],131072,air_time_monotonic_ns()+2000000000ull);
            if(data.tag!=AIR_TAG_OK){ok=0;break;}
            if(!data.u.ok.len){air_buf_free(&data.u.ok);ok=0;break;}
            for(uint64_t j=0;j<data.u.ok.len;++j)if(data.u.ok.ptr[j]!=expected(received+j))ok=0;
            received+=data.u.ok.len;air_buf_free(&data.u.ok);
        }
        drained+=received;
        if(received!=16u*sizeof payload)ok=0;
        air_net_tcp_close(senders[i]);air_net_tcp_close(receivers[i]);air_net_tcp_close(listeners[i]);
    }
    printf("\"resource_pool\":{\"pairs\":%u,\"connected_sockets\":%u,\"configured_send_room_sum\":%llu,\"queued_and_verified_bytes\":%llu,\"all_handles_closed\":true,\"passed\":%s}",count,count*2,(unsigned long long)room,(unsigned long long)drained,ok&&count==32?"true":"false");
    return ok&&count==32;
}
int main(int argc,char**argv) {
    if(argc>1 && strcmp(argv[1],"v6")==0){probe_host.ptr="::1";probe_host.len=3;}
    /* Initialize lazy Winsock/DNS state before checking this fixture's ownership. */
    air_result_socket ls=air_net_tcp_listen(probe_host,0,2);if(ls.tag!=AIR_TAG_OK)return 2;
    air_socket listener=ls.u.ok;
    air_result_port_net port=air_net_tcp_local_port(&listener);if(port.tag!=AIR_TAG_OK)return 2;
    air_result_socket cs=air_net_tcp_connect(probe_host,port.u.ok);if(cs.tag!=AIR_TAG_OK)return 2;
    air_result_socket as=air_net_tcp_accept_until(&listener,air_time_monotonic_ns()+2000000000ull);
    if(as.tag!=AIR_TAG_OK)return 2;
    air_net_tcp_close(cs.u.ok);air_net_tcp_close(as.u.ok);air_net_tcp_close(listener);
    DWORD before=0,after=0;
    if(!GetProcessHandleCount(GetCurrentProcess(),&before))return 2;
    puts("{");int ok=pool();
    if(!GetProcessHandleCount(GetCurrentProcess(),&after))return 2;
    if(after!=before)ok=0;
    printf(",\"handles_before\":%lu,\"handles_after\":%lu",(unsigned long)before,(unsigned long)after);
    printf(",\"passed\":%s}\n",ok?"true":"false");
    return ok?0:1;
}
