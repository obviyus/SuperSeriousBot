scp -r $TRAVIS_BUILD_DIR TG-bot@$HOSTNAME:/home/TG-bot/travis-testing
ssh -i /tmp/deploy_rsa TG-bot@$HOSTNAME  "screen -S WeirdIndiaBot -dm bash -c 'cd travis-testing; python3 main.py'"
