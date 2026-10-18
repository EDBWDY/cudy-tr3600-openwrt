/* Read cached WAPP_GET_SCAN_RESULTS only; does not trigger scanning or change radio settings.
 * ABI: mt_wifi 7.6.6.1, embedded/include/wapp/wapp_cmm_type.h.
 * Request 24, OID_WAPP_EVENT 0x0647, response 34.
 * bss_ops.c populates CentralChannel from HT/VHT operation IEs.
 * Output excludes SSID, keys and configuration. Eight-second upper bound.
 */
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <sys/file.h>
#include <fcntl.h>
#include <linux/wireless.h>
#include <linux/netlink.h>
#include <linux/rtnetlink.h>
#include <poll.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <errno.h>
#include <stdlib.h>
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static int decode(unsigned char*p,size_t n,int idx){
 if(n<12||p[1]!=34||u32(p+2)!=(unsigned)idx)return -1;
 unsigned count=p[11];
 if(!count)return 0;
 if(n<12+65*count)return -1;
 size_t stride=(n-12)/count;
 for(unsigned i=0;i<count;i++){
  unsigned char*b=p+12+i*stride;
  printf("%02x:%02x:%02x:%02x:%02x:%02x %u %u %u\n",b[0],b[1],b[2],b[3],b[4],b[5],b[6],b[7],b[61]);
 }
 return p[10]?1:0;
}
int main(int argc,char**argv){
 if(argc!=2||(strcmp(argv[1],"ra0")&&strcmp(argv[1],"rax0")))return 2;
 int lock=open("/var/lock/tr3000-scan-export.lock",O_CREAT|O_RDWR,0600);
 if(lock<0||flock(lock,LOCK_EX|LOCK_NB)<0)return 1;
 int sk=socket(AF_INET,SOCK_DGRAM,0),nl=socket(AF_NETLINK,SOCK_RAW,NETLINK_ROUTE);
 if(sk<0||nl<0){perror("socket");return 1;}
 struct ifreq ir={0};strncpy(ir.ifr_name,argv[1],IFNAMSIZ-1);
 if(ioctl(sk,SIOCGIFINDEX,&ir)<0){perror("ifindex");return 1;}
 int idx=ir.ifr_ifindex;
 struct sockaddr_nl sa={.nl_family=AF_NETLINK,.nl_groups=RTMGRP_LINK};
 if(bind(nl,(void*)&sa,sizeof(sa))<0){perror("bind");return 1;}
 uint8_t req[16]={24,14};uint32_t scan=(uint32_t)time(NULL)^(uint32_t)getpid();memcpy(req+2,&idx,4);memcpy(req+12,&scan,4);
 alarm(8);
 for(int page=0;page<128;page++){
  struct iwreq wr={0};strncpy(wr.ifr_name,argv[1],IFNAMSIZ-1);wr.u.data.pointer=req;wr.u.data.length=sizeof(req);wr.u.data.flags=0x8647;
  if(ioctl(sk,0x8be1,&wr)<0){perror("WAPP scan query");return 1;}
  int answer=-1;
  for(int retry=0;retry<10&&answer<0;retry++){
   struct pollfd fd={.fd=nl,.events=POLLIN};if(poll(&fd,1,500)<=0){fprintf(stderr,"WAPP response timeout\n");return 1;}
   unsigned char buf[32768];int len=recv(nl,buf,sizeof(buf),0);if(len<0)return 1;
   for(struct nlmsghdr*h=(void*)buf;NLMSG_OK(h,len);h=NLMSG_NEXT(h,len)){
    if(h->nlmsg_type!=RTM_NEWLINK)continue;
    struct ifinfomsg*ifi=NLMSG_DATA(h);int rem=IFLA_PAYLOAD(h);
    for(struct rtattr*a=IFLA_RTA(ifi);RTA_OK(a,rem);a=RTA_NEXT(a,rem)){
     if(a->rta_type!=IFLA_WIRELESS)continue;
     unsigned char*e=RTA_DATA(a);size_t left=RTA_PAYLOAD(a);
     while(left>=IW_EV_POINT_LEN){unsigned el=u16(e),cmd=u16(e+2);if(el<IW_EV_POINT_LEN||el>left)break;
      if(cmd==IWEVCUSTOM&&u16(e+IW_EV_LCP_LEN+2)==0x647){unsigned dl=u16(e+IW_EV_LCP_LEN);if(dl<=el-IW_EV_POINT_LEN)answer=decode(e+IW_EV_POINT_LEN,dl,idx);}
      e+=el;left-=el;
     }
    }
   }
  }
  if(answer<0)return 1;if(answer==0){close(sk);close(nl);return 0;}
 }
 return 1;
}
