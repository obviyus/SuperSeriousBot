#scp -r $TRAVIS_BUILD_DIR TG-bot@$HOSTNAME:/home/TG-bot/bot
echo $TRAVIS_BRANCH
ssh -i /tmp/deploy_rsa TG-bot@$HOSTNAME  "screen -X -S $2 quit || true && screen -S $2 -dm bash -c 'cd $1; git pull origin $3; python3 main.py'"
