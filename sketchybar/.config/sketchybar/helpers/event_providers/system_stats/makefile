bin/system_stats: system_stats.c cpu.h smc.h stats.h ../sketchybar.h | bin
	clang -std=c11 -O2 -Wall $< -framework IOKit -framework CoreFoundation -o $@

bin:
	mkdir bin
