#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    if (argc != 4) return 2;
    int32_t offset = (int32_t) strtoll(argv[1], NULL, 10);
    int32_t length = (int32_t) strtoll(argv[2], NULL, 10);
    int32_t total = (int32_t) strtoll(argv[3], NULL, 10);
    int32_t end = offset + length;
    int accepted = offset >= 0 && length >= 0 && end <= total;
    printf("before offset=%d length=%d total=%d end=%d decision=%s\n",
           offset, length, total, end, accepted ? "ACCEPT" : "REJECT");
    return accepted ? 0 : 1;
}
