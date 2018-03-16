START_MONGO = bash mongo.sh
KS_RUN = bash -c "ks_server.py --data-dir /opt/svc/data --console-log-level 'info' --log-dir 'key_server_logs' 2>&1 >> ks_server.log &"

dependencies_run:
	@$(KS_RUN)

start_mongo:
	@$(START_MONGO)

check:
	@(python3 version_check.py)

install: check
	pip3 install -r requirements.txt

run: check start_mongo
	@(python3 main.py)
