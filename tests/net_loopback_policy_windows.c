#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <windows.h>
#include <stdio.h>
#include "air_rt.h"
static int fault=0,send_room_sets=0;
static int WSAAPI controlled_set(SOCKET s,int level,int name,const char*v,int len) {
    if(level==SOL_SOCKET&&name==SO_SNDBUF)++send_room_sets;
    if(fault==1&&level==SOL_SOCKET&&name==SO_SNDBUF){WSASetLastError(WSAEINVAL);return SOCKET_ERROR;}
    return setsockopt(s,level,name,v,len);
}
static int WSAAPI controlled_get(SOCKET s,int level,int name,char*v,int*len) {
    int result=getsockopt(s,level,name,v,len);
    if(fault==2&&result==0&&level==SOL_SOCKET&&name==SO_SNDBUF)*(int*)v=65536;
    if(fault==4&&result==0&&level==SOL_SOCKET&&name==SO_SNDBUF)*len=1;
    return result;
}
static int WSAAPI controlled_peer(SOCKET s,struct sockaddr*v,int*len) {
    if(fault==3){WSASetLastError(WSAENOTCONN);return SOCKET_ERROR;}
    int result=getpeername(s,v,len);
    // Pure policy witness: simulate OS-reported remote metadata over a real local
    // connection; no external host is contacted by this component fixture.
    if(fault==5&&result==0&&v->sa_family==AF_INET)((struct sockaddr_in*)v)->sin_addr.s_addr=htonl(0x0a000001u);
    return result;
}
#define setsockopt controlled_set
#define getsockopt controlled_get
#define getpeername controlled_peer
#ifndef GENESIS_NET_SOURCE
#error GENESIS_NET_SOURCE must name the Windows AIR TCP provider
#endif
#include GENESIS_NET_SOURCE
#undef setsockopt
#undef getsockopt
#undef getpeername
int main(void) {
    int checks=0,failures=0;DWORD before=0,after=0;
    air_view host={"127.0.0.1",9};
    /* Warm complete successful connect/accept (including lazy DNS/Winsock state),
       not just listen, before measuring fresh-socket failure leaks. */
    air_result_socket warm=air_net_tcp_listen(host,0,2);
    if(warm.tag!=AIR_TAG_OK)return 2;air_socket wl=warm.u.ok;
    air_result_port_net wp=air_net_tcp_local_port(&wl);if(wp.tag!=AIR_TAG_OK)return 2;
    air_result_socket wc=air_net_tcp_connect(host,wp.u.ok);if(wc.tag!=AIR_TAG_OK)return 2;
    air_result_socket wa=air_net_tcp_accept_until(&wl,air_time_monotonic_ns()+1000000000ull);if(wa.tag!=AIR_TAG_OK)return 2;
    air_net_tcp_close(wc.u.ok);air_net_tcp_close(wa.u.ok);air_net_tcp_close(wl);
    GetProcessHandleCount(GetCurrentProcess(),&before);
    for(int mode=1;mode<=4;++mode)for(int side=0;side<2;++side){
        fault=0;air_result_socket ls=air_net_tcp_listen(host,0,2);if(ls.tag!=AIR_TAG_OK)return 3;
        air_socket listener=ls.u.ok;air_result_port_net port=air_net_tcp_local_port(&listener);if(port.tag!=AIR_TAG_OK)return 4;
        fault=side==0?mode:0;air_result_socket cs=air_net_tcp_connect(host,port.u.ok);
        if(side==0){++checks;if(cs.tag!=AIR_TAG_ERR||cs.u.err.code!=AIR_NET_IO)++failures;
            fault=0;air_result_socket as=air_net_tcp_accept_until(&listener,air_time_monotonic_ns()+1000000000ull);
            if(as.tag==AIR_TAG_OK){air_socket receiver=as.u.ok;air_result_buf_net d=air_net_tcp_recv_until(&receiver,1,air_time_monotonic_ns()+1000000000ull);
                ++checks;if(d.tag!=AIR_TAG_OK||d.u.ok.len!=0)++failures;if(d.tag==AIR_TAG_OK)air_buf_free(&d.u.ok);air_net_tcp_close(receiver);
            }else ++failures;
        }else{
            if(cs.tag!=AIR_TAG_OK)return 5;air_socket sender=cs.u.ok;
            fault=mode;air_result_socket as=air_net_tcp_accept_until(&listener,air_time_monotonic_ns()+1000000000ull);
            ++checks;if(as.tag!=AIR_TAG_ERR||as.u.err.code!=AIR_NET_IO)++failures;
            fault=0;air_result_buf_net d=air_net_tcp_recv_until(&sender,1,air_time_monotonic_ns()+1000000000ull);
            ++checks;if(d.tag!=AIR_TAG_OK||d.u.ok.len!=0)++failures;if(d.tag==AIR_TAG_OK)air_buf_free(&d.u.ok);air_net_tcp_close(sender);
        }
        air_net_tcp_close(listener);
    }
    fault=0;air_result_socket rs=air_net_tcp_listen(host,0,2);if(rs.tag!=AIR_TAG_OK)return 6;
    air_socket rl=rs.u.ok;air_result_port_net rp=air_net_tcp_local_port(&rl);if(rp.tag!=AIR_TAG_OK)return 7;
    int default_room=0,len=sizeof default_room;
    if(getsockopt(native_socket(&rl),SOL_SOCKET,SO_SNDBUF,(char*)&default_room,&len)!=0)return 8;
    send_room_sets=0;fault=5;air_result_socket rc=air_net_tcp_connect(host,rp.u.ok);if(rc.tag!=AIR_TAG_OK)return 9;
    air_result_socket ra=air_net_tcp_accept_until(&rl,air_time_monotonic_ns()+1000000000ull);if(ra.tag!=AIR_TAG_OK)return 10;
    int remote_send=0,remote_accept=0;len=sizeof remote_send;
    getsockopt(native_socket(&rc.u.ok),SOL_SOCKET,SO_SNDBUF,(char*)&remote_send,&len);len=sizeof remote_accept;
    getsockopt(native_socket(&ra.u.ok),SOL_SOCKET,SO_SNDBUF,(char*)&remote_accept,&len);
    ++checks;if(send_room_sets!=0)++failures;
    ++checks;if(remote_send!=default_room||remote_accept!=default_room)++failures;
    fault=0;air_net_tcp_close(rc.u.ok);air_net_tcp_close(ra.u.ok);air_net_tcp_close(rl);
    GetProcessHandleCount(GetCurrentProcess(),&after);++checks;if(after!=before)++failures;
    printf("{\"checks\":%d,\"failures\":%d,\"handles_before\":%lu,\"handles_after\":%lu,\"passed\":%s}\n",checks,failures,(unsigned long)before,(unsigned long)after,failures?"false":"true");
    return failures?1:0;
}
