/* X68 V0113 display-only replacement. No charger, GPIO, flash or USB writes.
 * The original LCD transport and its ready guard remain in use.
 * Fixed addresses are valid ONLY for the hash-gated V0113 image.
 */
typedef unsigned char u8;
typedef unsigned int u32;
#ifdef SCREEN_HOST
__declspec(dllexport) u8 framebuffer[30720];
__declspec(dllexport) u8 background[30720];
__declspec(dllexport) u8 rtc[9];
__declspec(dllexport) u32 tick;
__declspec(dllexport) u8 battery_level;
__declspec(dllexport) u8 media_data[245760];
__declspec(dllexport) u8 media_mode,media_count;
__declspec(dllexport) u32 media_period;
static u8 read_clock(int reg) { return rtc[reg]; }
#define FB framebuffer
#define BG background
#else
#define FB ((volatile u8 *)0x000819e0)
#define BG ((const u8 *)0x20031664)
static u8 read_clock(int reg) { return ((u8 (*)(int))0x2000f4f4)(reg); }
#endif

static const u8 numbers[10][7] = {
 {14,17,19,21,25,17,14}, {4,12,4,4,4,4,14},
 {14,17,1,2,4,8,31}, {30,1,1,14,1,1,30},
 {2,6,10,18,31,2,2}, {31,16,16,30,1,1,30},
 {14,16,16,30,17,17,14}, {31,1,2,4,8,8,8},
 {14,17,17,14,17,17,14}, {14,17,17,15,1,1,14}
};
static void pixel(int x,int y,unsigned color) {
 if ((unsigned)x>=160 || (unsigned)y>=96) return;
 unsigned n=(unsigned)(y*160+x)*2;
 FB[n]=(u8)(color>>8); FB[n+1]=(u8)color;
}
static void digit(int n,int x,int y,int scale,unsigned color) {
 if ((unsigned)n>9) return;
 for(int row=0;row<7;row++) for(int col=0;col<5;col++)
  if(numbers[n][row] & (16>>col))
   for(int dy=0;dy<scale;dy++) for(int dx=0;dx<scale;dx++)
    pixel(x+col*scale+dx,y+row*scale+dy,color);
}
static void pair(u8 bcd,int x,int y,int scale,unsigned color) {
 digit((bcd>>4)&15,x,y,scale,color);
 digit(bcd&15,x+6*scale,y,scale,color);
}
#ifdef SCREEN_HOST
__declspec(dllexport)
#endif
void render(void) {
#ifndef SCREEN_HOST
 /* Original routine sends a pending framebuffer through the original LCD bus. */
 /* In original screen mode 0 the transport also requires this display request
  * flag. Retain the transport's own clearing/ready behavior, rather than
  * allowing the first pending image to block every subsequent redraw. */
 if (*(volatile u8 *)0x00080c9a & 128)
  *(volatile u8 *)0x00080d20 |= 16;
 ((void (*)(void))0x00006eac)();
 if (*(volatile u8 *)0x00080cf1) return;
 if (*(volatile u8 *)0x00080c9a & 128) return;
 /* Only explicit custom-media mode is separate; all old default modes use
  * the same Lavender desktop. Physical flash reads use the stock callback. */
 if(*(volatile u8 *)0x00080571==4){
  unsigned count=*(volatile u8 *)0x00080572;
  unsigned period=*(volatile u8 *)0x0008057a|((unsigned)*(volatile u8 *)0x0008057b<<8);
  if(count<1 || count>8 || period<50 || period>5000)return;
  unsigned frame=(*(volatile u32 *)0x80140200/(period*16000))%count;
  if(*(volatile u8 *)0x00080d82==212 && *(volatile u8 *)0x00080d49==frame)return;
  void (*read_flash)(u32,u32,volatile u8 *)=*(void (**)(u32,u32,volatile u8 *))0x00000bb4;
  read_flash(0x000a2000+frame*30720,30720,FB);
  *(volatile u8 *)0x00080d49=(u8)frame;*(volatile u8 *)0x00080d82=212;
  *(volatile u8 *)0x00080c9a|=128;return;
 }
 *(volatile u8 *)0x00080d82=0;
#endif
#ifdef SCREEN_HOST
 if(media_mode==4 && media_count>=1 && media_count<=8 && media_period>=50 && media_period<=5000){
  unsigned frame=(tick/(media_period*16000))%media_count;
  for(unsigned i=0;i<30720;i++)FB[i]=media_data[frame*30720+i];return;
 }
 u8 second=read_clock(2),minute=read_clock(3),hour=read_clock(4)&63;
 u8 day=read_clock(5),month=read_clock(7)&31;
 u32 phase=tick/4000000;
#else
 /* Retired native RTC/current and previous-clock caches, not new RAM.
  * Keep an independently ticking software
  * clock from explicitly synced date/time parameters and the running 16 MHz
  * MCU system timer. No guessed battery values and no RTC/GPIO writes.
  */
 volatile u8 *snapshot=(volatile u8 *)0x00080d8c;
 volatile u8 *clock_cache=(volatile u8 *)0x00080b80;
 const volatile u8 *param=(const volatile u8 *)0x00080573;
 u32 now=*(volatile u32 *)0x80140200;
 u32 phase=now/4000000;
 int reset=(snapshot[6]&252)!=164;
 for(unsigned i=0;i<6;i++) if(snapshot[i]!=param[i])reset=1;
 if(!reset && (snapshot[6]&3)==(phase&3) &&
    now-*(volatile u32 *)clock_cache<16000000)return;
 if(reset){
  for(unsigned i=0;i<6;i++)snapshot[i]=param[i];
  *(volatile u32 *)clock_cache=now;
  clock_cache[4]=0;clock_cache[5]=0;clock_cache[6]=0;
 }
 snapshot[6]=(u8)(164|(phase&3));
 u32 previous=*(volatile u32 *)clock_cache;
 u32 steps=(now-previous)/16000000;
 u32 elapsed=(u32)clock_cache[4]|((u32)clock_cache[5]<<8)|((u32)clock_cache[6]<<16);
 if(steps){
  elapsed=(elapsed+steps)&0xffffff;
  *(volatile u32 *)clock_cache=previous+steps*16000000;
  clock_cache[4]=(u8)elapsed;clock_cache[5]=(u8)(elapsed>>8);clock_cache[6]=(u8)(elapsed>>16);
 }
 u32 total=((snapshot[2]>>4)*10+(snapshot[2]&15))*3600+
           ((snapshot[1]>>4)*10+(snapshot[1]&15))*60+
           ((snapshot[0]>>4)*10+(snapshot[0]&15))+elapsed;
 unsigned ss=total%60,mm=(total/60)%60,hh=(total/3600)%24;
 u8 second=(u8)((ss/10)*16+ss%10),minute=(u8)((mm/10)*16+mm%10),hour=(u8)((hh/10)*16+hh%10);
 u8 day=snapshot[4],month=snapshot[5];
#endif
 for(unsigned i=0;i<30720;i++) FB[i]=BG[i];
 /* Time from synced parameters + MCU time; never a painted sample clock. */
 pair(hour,10,24,2,0xf7bf); pair(minute,39,24,2,0xf7bf);
 pixel(35,28,0x7f7b);pixel(35,33,0x7f7b);
 pair(second,67,31,1,0x7f7b);
 pair(day,108,24,1,0xe51f);pair(month,127,24,1,0xe51f);
 pixel(122,27,0xe51f);pixel(121,28,0xe51f);pixel(120,29,0xe51f);
 /* Idle sprite: a slow eye blink, scarf flutter and a spinning gold coin. */
 if((phase%16)<2){
  pixel(107,57,0xb79b);pixel(112,57,0xb79b);
  pixel(106,58,0x20c6);pixel(107,58,0x20c6);pixel(111,58,0x20c6);pixel(112,58,0x20c6);
 }
 if(phase&1){pixel(117,62,0x1712);pixel(118,62,0x1712);pixel(117,60,0xed3b);pixel(118,60,0xed3b);}
 for(int y=62;y<=68;y++)for(int x=132;x<=135;x++)pixel(x,y,0x10a5);
 int half=(phase%4==0)?2:((phase%4==2)?0:1);
 for(int y=63;y<=67;y++)for(int x=133-half;x<=133+half;x++)pixel(x,y,0xf6b1);
 /* Cached firmware indicator, never a synthesized charge measurement.
  * Replace PLAYER 1 with a compact battery badge. No charge-state claim. */
#ifdef SCREEN_HOST
 unsigned level=battery_level;
#else
 unsigned level=*(volatile u8 *)0x00080b70;
#endif
 for(int y=86;y<=94;y++)for(int x=53;x<=106;x++)pixel(x,y,0x6a90);
 unsigned ink=level<=100?0xb79b:0xc638;
 for(int x=55;x<=67;x++){pixel(x,87,ink);pixel(x,93,ink);}
 for(int y=87;y<=93;y++){pixel(55,y,ink);pixel(67,y,ink);}
 for(int y=89;y<=91;y++)pixel(68,y,ink);
 if(level<=100){
  for(int y=89;y<=91;y++)for(unsigned x=57;x<57+(level*9/100);x++)pixel(x,y,ink);
  if(level==100)digit(1,72,87,1,ink);
  digit((level/10)%10,78,87,1,ink);digit(level%10,84,87,1,ink);
 }else for(int x=78;x<=88;x++)if(x<82 || x>84)pixel(x,90,ink);
 pixel(91,87,ink);pixel(92,88,ink);pixel(95,92,ink);pixel(96,93,ink);
 for(int i=0;i<5;i++)pixel(96-i,87+i,ink);
#ifndef SCREEN_HOST
 *(volatile u8 *)0x00080c9a |= 128;
#endif
}

#ifndef SCREEN_HOST
/* Read-only diagnostic snapshot. Exact addresses come from the original ADC
 * routine and battery report. Reads cached samples; never initiates ADC, writes
 * GPIO, changes charge controls, calibrates or guesses battery voltage. */
__attribute__((used,noinline)) void battery_diagnostic(volatile u8 *packet) {
 if(packet[0]!=4 || packet[3]!=25 || packet[4]!=48 || packet[5] || packet[6] || packet[7]){packet[7]=255;return;}
 volatile u8 *out=packet+8;
 out[0]='X';out[1]='B';out[2]='D';out[3]=1;
 out[4]=*(volatile u8 *)0x80b70;out[5]=*(volatile u8 *)0x808d3;
 out[6]=*(volatile u8 *)0x80140320;out[7]=*(volatile u8 *)0x80140310;
 out[8]=*(volatile u8 *)0x80d01;out[9]=*(volatile u8 *)0x80c9c;
 out[10]=*(volatile u8 *)0x80d30;out[11]=*(volatile u8 *)0x80d31;
 for(unsigned i=0;i<16;i++)out[12+i]=((volatile u8 *)0x80d9c)[i];
 for(unsigned i=0;i<10;i++)out[28+i]=((volatile u8 *)0x1130)[i];
 for(unsigned i=0;i<4;i++)out[38+i]=((volatile u8 *)0x80d40)[i];
 u32 now=*(volatile u32 *)0x80140200;
 for(unsigned i=0;i<4;i++)out[42+i]=(u8)(now>>(8*i));
 out[46]=*(volatile u8 *)0x80bfe;out[47]=*(volatile u8 *)0x80cfd;
}
__attribute__((used,naked)) void battery_bridge(void) {
 __asm__ volatile(
 "addi sp,sp,-64\n"
 "sw ra,0(sp)\n sw t0,4(sp)\n sw t1,8(sp)\n sw t2,12(sp)\n"
 "sw a0,16(sp)\n sw a1,20(sp)\n sw a2,24(sp)\n sw a3,28(sp)\n"
 "sw a4,32(sp)\n sw a5,36(sp)\n sw a6,40(sp)\n sw a7,44(sp)\n"
 "sw t3,48(sp)\n sw t4,52(sp)\n sw t5,56(sp)\n sw t6,60(sp)\n"
 "mv a0,s0\n call battery_diagnostic\n"
 "lw ra,0(sp)\n lw t0,4(sp)\n lw t1,8(sp)\n lw t2,12(sp)\n"
 "lw a0,16(sp)\n lw a1,20(sp)\n lw a2,24(sp)\n lw a3,28(sp)\n"
 "lw a4,32(sp)\n lw a5,36(sp)\n lw a6,40(sp)\n lw a7,44(sp)\n"
 "lw t3,48(sp)\n lw t4,52(sp)\n lw t5,56(sp)\n lw t6,60(sp)\n"
 "addi sp,sp,64\n j stock_ack\n"
 );
}
/* Report 04 / command 18: exact six-byte RAM-only clock update. The bridge
 * preserves every caller-saved register expected by the original dispatcher,
 * then rejoins its existing ACK path. No flash-dirty flag or RTC write. */
__attribute__((used,noinline)) void clock_command(volatile u8 *packet) {
 int valid=packet[0]==4 && packet[3]==24 && packet[4]==6 &&
           packet[5]==0 && packet[6]==0 && packet[7]==0;
 const u8 maximum[6]={59,59,23,7,31,12};
 for(unsigned i=0;i<6;i++){
  unsigned b=packet[8+i],value=(b>>4)*10+(b&15);
  if((b&15)>9 || (b>>4)>9 || value>maximum[i] || (i>=3 && value==0))valid=0;
 }
 if(!valid){packet[7]=255;return;}
 volatile u8 *param=(volatile u8 *)0x00080573;
 for(unsigned i=0;i<6;i++)param[i]=packet[8+i];
 *(volatile u8 *)0x00080d92=0;
}
__attribute__((used,naked)) void clock_bridge(void) {
 __asm__ volatile(
 "addi sp,sp,-64\n"
 "sw ra,0(sp)\n sw t0,4(sp)\n sw t1,8(sp)\n sw t2,12(sp)\n"
 "sw a0,16(sp)\n sw a1,20(sp)\n sw a2,24(sp)\n sw a3,28(sp)\n"
 "sw a4,32(sp)\n sw a5,36(sp)\n sw a6,40(sp)\n sw a7,44(sp)\n"
 "sw t3,48(sp)\n sw t4,52(sp)\n sw t5,56(sp)\n sw t6,60(sp)\n"
 "mv a0,s0\n call clock_command\n"
 "lw ra,0(sp)\n lw t0,4(sp)\n lw t1,8(sp)\n lw t2,12(sp)\n"
 "lw a0,16(sp)\n lw a1,20(sp)\n lw a2,24(sp)\n lw a3,28(sp)\n"
 "lw a4,32(sp)\n lw a5,36(sp)\n lw a6,40(sp)\n lw a7,44(sp)\n"
 "lw t3,48(sp)\n lw t4,52(sp)\n lw t5,56(sp)\n lw t6,60(sp)\n"
 "addi sp,sp,64\n"
 /* Direct JAL x0 avoids clobbering a just-restored temporary register. */
 "j stock_ack\n"
 );
}
#endif
