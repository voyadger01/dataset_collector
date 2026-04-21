CC = gcc
CFLAGS = -Wall -O2
OUT = calculator

all: $(OUT)

$(OUT): src/main.c src/math_ops.c
	$(CC) $(CFLAGS) -I src -o $(OUT) src/main.c src/math_ops.c
