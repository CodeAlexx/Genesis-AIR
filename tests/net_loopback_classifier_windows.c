#ifndef GENESIS_NET_SOURCE
#error GENESIS_NET_SOURCE must name the Windows AIR TCP provider
#endif
#include GENESIS_NET_SOURCE
static int checks=0, failures=0;
static void check(int value,int expected,const char*name) {
    ++checks;if(value!=expected){++failures;fprintf(stderr,"%s: %d != %d\n",name,value,expected);}
}
int main(void) {
    struct sockaddr_storage peer;
    memset(&peer,0,sizeof peer);struct sockaddr_in *v4=(struct sockaddr_in*)&peer;v4->sin_family=AF_INET;
    const uint32_t addr[]={0x7f000001u,0x7fffffffu,0x7f000000u,0x7e000001u,0x80000001u,0x0a000001u,0xc0a80101u,0u};
    const int want[]={1,1,1,0,0,0,0,0};
    for(unsigned i=0;i<8;++i){v4->sin_addr.s_addr=htonl(addr[i]);check(classify_loopback_peer(&peer,sizeof*v4),want[i],"IPv4");}
    check(classify_loopback_peer(&peer,sizeof*v4-1),-1,"Truncated IPv4");
    memset(&peer,0,sizeof peer);struct sockaddr_in6 *v6=(struct sockaddr_in6*)&peer;v6->sin6_family=AF_INET6;
    unsigned char *bytes=(unsigned char*)&v6->sin6_addr;
    bytes[15]=1;check(classify_loopback_peer(&peer,sizeof*v6),1,"IPv6 ::1");
    bytes[15]=2;check(classify_loopback_peer(&peer,sizeof*v6),0,"IPv6 ::2");
    bytes[15]=0;check(classify_loopback_peer(&peer,sizeof*v6),0,"IPv6 unspecified");
    bytes[0]=0x20;bytes[1]=1;bytes[15]=1;check(classify_loopback_peer(&peer,sizeof*v6),0,"Remote IPv6");
    memset(bytes,0,16);bytes[10]=bytes[11]=255;bytes[12]=127;bytes[15]=1;
    check(classify_loopback_peer(&peer,sizeof*v6),1,"Mapped IPv4 loopback");
    bytes[12]=126;check(classify_loopback_peer(&peer,sizeof*v6),0,"Mapped remote IPv4");
    bytes[10]=bytes[11]=0;bytes[12]=127;check(classify_loopback_peer(&peer,sizeof*v6),0,"Compatible not mapped IPv4");
    check(classify_loopback_peer(&peer,sizeof*v6-1),-1,"Truncated IPv6");
    peer.ss_family=AF_UNSPEC;check(classify_loopback_peer(&peer,sizeof peer),-1,"Unknown family");
    check(classify_loopback_peer(&peer,0),-1,"Empty address");check(classify_loopback_peer(NULL,0),-1,"Null address");
    printf("{\"schema\":\"genesis.windows.loopback-classifier.v1\",\"checks\":%d,\"failures\":%d,\"passed\":%s}\n",checks,failures,failures?"false":"true");
    return failures?1:0;
}
