#!/bin/bash

echo "⚠️ 긴급 롤백을 시작합니다..."

# 1. 바로 직전 커밋으로 되돌리기
git reset --hard HEAD@{1}

# 2. 서비스 재시작
sudo systemctl restart discordbot

echo "⏪ 롤백 완료!"
