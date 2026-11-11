# Clear SDK settings a launched bar can inherit after an OS upgrade.
bin/ai_usage: main.swift usage_format.swift | bin
	env -u SDKROOT -u MACOSX_DEPLOYMENT_TARGET /usr/bin/xcrun --sdk macosx swiftc -O main.swift usage_format.swift -o $@

bin:
	mkdir bin
