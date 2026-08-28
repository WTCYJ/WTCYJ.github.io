#include <stdint.h>
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "safe") == 0) {
        volatile int32_t value = 41;
        printf("safe-result=%d\n", value + 1);
        return 0;
    }
    if (argc == 2 && strcmp(argv[1], "overflow") == 0) {
        volatile int32_t value = INT32_MAX;
        printf("overflow-result=%d\n", value + 1);
        return 0;
    }
    fprintf(stderr, "usage: %s safe|overflow\n", argv[0]);
    return 2;
}
