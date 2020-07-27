#scp -r $TRAVIS_BUILD_DIR TG-bot@$HOSTNAME:/home/TG-bot/bot
ssh -i /tmp/deploy_rsa TG-bot@$HOSTNAME  "screen -X -S superseriousbot quit || true && screen -S superseriousbot -dm bash -c 'cd bot; git pull origin $3; python3 main.py'"
