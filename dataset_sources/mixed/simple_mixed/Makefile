CC = gcc
CXX = g++

all: simple_mixed

simple_mixed: math_lib.c main.cpp
	$(CC) -c math_lib.c -o math_lib.o
	$(CXX) -c main.cpp -o main.o
	$(CXX) main.o math_lib.o -o simple_mixed

clean:
	rm -f *.o simple_mixed

.PHONY: all clean