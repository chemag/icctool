


simple.bin: samsung.bin
	./icctool.py --remove-copyright --write $^ $@

xxd: simple.bin
	xxd -i -a $^
