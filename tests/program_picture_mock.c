#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <signal.h>
#include <sys/time.h>
typedef int SOCKET;
#define INVALID_SOCKET (-1)
#define closesocket close
#define GetCurrentProcessId() ((unsigned long)getpid())
#define Sleep(ms) usleep((ms)*1000)
#endif
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
static int send_all(SOCKET s,const unsigned char *p,size_t n){while(n){int r=send(s,(const char*)p,(int)n,0);if(r<=0)return 0;p+=r;n-=r;}return 1;}
static void put64(unsigned char*p,uint64_t n){for(int i=0;i<8;i++){p[i]=(unsigned char)n;n>>=8;}}
static void put32(unsigned char*p,uint32_t n){for(int i=0;i<4;i++){p[i]=(unsigned char)n;n>>=8;}}
static void mode(char*out,size_t n){const char*p=getenv("PROGRAM_MOCK_MODE_FILE");FILE*f=p?fopen(p,"rb"):NULL;if(!f){strcpy(out,"valid");return;}size_t got=fread(out,1,n-1,f);out[got]=0;fclose(f);}
static void witness(uint64_t token,uint64_t seq){const char*p=getenv("PROGRAM_MOCK_WITNESS");if(p){FILE*f=fopen(p,"ab");if(f){fprintf(f,"%lu\t%llu\t%llu\n",GetCurrentProcessId(),(unsigned long long)token,(unsigned long long)seq);fclose(f);}}}
int main(void){
#ifdef _WIN32
WSADATA w;if(WSAStartup(MAKEWORD(2,2),&w))return 2;
#else
signal(SIGPIPE,SIG_IGN);
#endif
SOCKET held=INVALID_SOCKET;char line[65536];while(fgets(line,sizeof line,stdin)){char kw[32];unsigned width,height,port;unsigned long long tok,seq;char kind[64];mode(kind,sizeof kind);if(sscanf(line,"%31s %u %u %u %llu %llu",kw,&width,&height,&port,&tok,&seq)!=6||strncmp(kw,"PREVIEWTCP",10)){puts("ERR");fflush(stdout);continue;}int keep=!strcmp(kw,"PREVIEWTCPKEEP");SOCKET s=held;if(s==INVALID_SOCKET){s=socket(AF_INET,SOCK_STREAM,IPPROTO_TCP);struct sockaddr_in a;memset(&a,0,sizeof a);a.sin_family=AF_INET;a.sin_addr.s_addr=htonl(INADDR_LOOPBACK);a.sin_port=htons((unsigned short)port);if(connect(s,(struct sockaddr*)&a,sizeof a)){closesocket(s);puts("ERR");fflush(stdout);continue;}
#ifdef _WIN32
DWORD ms=3000;
#else
struct timeval ms={3,0};
#endif
setsockopt(s,SOL_SOCKET,SO_SNDTIMEO,(char*)&ms,sizeof ms);if(keep)held=s;}
unsigned char header[40]={0},footer[32]={0},pixels[1024];for(unsigned y=0;y<16;y++)for(unsigned x=0;x<16;x++){size_t at=(y*16+x)*4;pixels[at]=pixels[at+1]=pixels[at+2]=(x+y)%2?0:255;pixels[at+3]=255;}memcpy(header,"GAPIX001",8);put64(header+8,tok);put64(header+16,seq);put32(header+24,width);put32(header+28,height);put64(header+32,1024);memcpy(footer,"GAPIEND1",8);put64(footer+8,tok);put64(footer+16,seq);put64(footer+24,1024);
if(!strcmp(kind,"wrong-token"))put64(header+8,tok+1);if(!strcmp(kind,"wrong-ticket"))put64(header+16,seq+1);if(!strcmp(kind,"wrong-dims"))put32(header+24,width+1);if(!strcmp(kind,"wrong-size"))put64(header+32,1025);if(!strcmp(kind,"wrong-magic"))header[0]='X';if(!strcmp(kind,"wrong-footer"))footer[0]='X';if(!strcmp(kind,"wrong-footer-token"))put64(footer+8,tok+1);if(!strcmp(kind,"wrong-footer-ticket"))put64(footer+16,seq+1);if(!strcmp(kind,"wrong-footer-size"))put64(footer+24,1025);if(!strcmp(kind,"exit")){closesocket(s);break;}
send_all(s,header,40);witness(tok,seq);
if(!strcmp(kind,"partial")){send_all(s,pixels,1);Sleep(10000);break;}
if(!strcmp(kind,"slow-valid"))Sleep(250);
if(!strcmp(kind,"truncated")){send_all(s,pixels,17);closesocket(s);held=INVALID_SOCKET;puts("DONE");fflush(stdout);continue;}
send_all(s,pixels,1024);if(keep)send_all(s,footer,32);if(!strcmp(kind,"extra")||!strcmp(kind,"legacy-extra"))send_all(s,(const unsigned char*)"X",1);
if(!keep){closesocket(s);printf("DONE -\n");}else printf("DONE TCPKEEP %llu %llu %u %u 1024\n",tok,!strcmp(kind,"wrong-done")?seq+1:seq,width,height);fflush(stdout);
if(!strcmp(kind,"delayed-extra")){Sleep(100);send_all(s,(const unsigned char*)"X",1);}
}if(held!=INVALID_SOCKET)closesocket(held);
#ifdef _WIN32
WSACleanup();
#endif
return 0;}
