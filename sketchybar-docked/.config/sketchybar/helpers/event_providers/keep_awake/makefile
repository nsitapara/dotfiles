# Clear SDK settings a launched bar can inherit after an OS upgrade.
bin/keep_awake: main.swift keep_awake_logic.swift | bin
	env -u SDKROOT -u MACOSX_DEPLOYMENT_TARGET /usr/bin/xcrun --sdk macosx swiftc -O main.swift keep_awake_logic.swift -o $@

bin:
	mkdir bin
