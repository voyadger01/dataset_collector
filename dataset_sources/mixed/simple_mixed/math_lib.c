#include <stdio.h>

int add(int a, int b) {
    return a + b;
}

int multiply(int a, int b) {
    return a * b;
}

void print_result(const char* operation, int result) {
    printf("%s: %d\n", operation, result);
}