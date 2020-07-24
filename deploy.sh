scp -r $TRAVIS_BUILD_DIR TG-bot@$HOSTNAME:/home/TG-bot/bot
ssh -i /tmp/deploy_rsa TG-bot@$HOSTNAME  "screen -X -S SuperSeriousBot quit || true && screen -S SuperSeriousBot -dm bash -c 'cd bot; python3 main.py'"
