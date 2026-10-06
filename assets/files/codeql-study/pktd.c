/* pktd.c - CodeQL 실습용 작은 패킷 처리기. 일부러 취약하게 만들었다. */
#include <arpa/inet.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static char buf[256];

/* 길이 필드를 그대로 믿는다: 원격 길이 -> memcpy 크기 */
void handle_echo(const unsigned char *pkt, size_t n)
{
    uint32_t len = ntohl(*(const uint32_t *)pkt);
    memcpy(buf, pkt + 4, len);
    write(1, buf, len);
}

/* 길이를 검사한 뒤 복사한다: 걸리면 안 되는 경우 */
void handle_name(const unsigned char *pkt, size_t n)
{
    uint16_t len = ntohs(*(const uint16_t *)pkt);
    if (len > sizeof(buf))
        return;
    memcpy(buf, pkt + 2, len);
}

/* 함수를 하나 건너서 흐른다: 함수 경계를 넘는 추적이 필요하다 */
static void copy_payload(const unsigned char *src, unsigned size)
{
    memcpy(buf, src, size);
}

void handle_data(const unsigned char *pkt, size_t n)
{
    unsigned size = ntohs(*(const uint16_t *)(pkt + 2)) - 4;
    copy_payload(pkt + 4, size);
}

int main(void)
{
    unsigned char pkt[2048];
    ssize_t n = read(0, pkt, sizeof(pkt));
    if (n < 4)
        return 1;
    switch (pkt[0]) {
    case 'E': handle_echo(pkt + 1, n - 1); break;
    case 'N': handle_name(pkt + 1, n - 1); break;
    case 'D': handle_data(pkt + 1, n - 1); break;
    }
    return 0;
}
