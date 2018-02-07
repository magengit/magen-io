check:
	@(python3 version_check.py)

install: check
	pip3 install -r requirements.txt

run: check
	@(python3 main.py)
