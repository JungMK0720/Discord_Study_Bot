#!/bin/bash

echo "🚀 배포를 시작합니다..."

# 1. 최신 코드 가져오기
git pull origin main

# 2. 서비스 재시작
sudo systemctl restart discordbot

# 3. 상태 확인
sleep 2
sudo systemctl status discordbot --no-pager

echo "✅ 배포 완료!"
