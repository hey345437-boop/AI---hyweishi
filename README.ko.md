# (・ω・) HyWeiShi (何以为势)

<div align="center">

<img src="https://img.shields.io/badge/AI-Powered-blueviolet?style=for-the-badge&logo=openai&logoColor=white" alt="AI Powered"/>
<img src="https://img.shields.io/badge/Crypto-Futures-orange?style=for-the-badge&logo=bitcoin&logoColor=white" alt="Crypto Futures"/>
<img src="https://img.shields.io/badge/Trading-Bot-success?style=for-the-badge&logo=robot&logoColor=white" alt="Trading Bot"/>

<br/><br/>

<pre>
██╗  ██╗██╗   ██╗██╗    ██╗███████╗██╗███████╗██╗  ██╗██╗
██║  ██║╚██╗ ██╔╝██║    ██║██╔════╝██║██╔════╝██║  ██║██║
███████║ ╚████╔╝ ██║ █╗ ██║█████╗  ██║███████╗███████║██║
██╔══██║  ╚██╔╝  ██║███╗██║██╔══╝  ██║╚════██║██╔══██║██║
██║  ██║   ██║   ╚███╔███╔╝███████╗██║███████║██║  ██║██║
╚═╝  ╚═╝   ╚═╝    ╚══╝╚══╝ ╚══════╝╚═╝╚══════╝╚═╝  ╚═╝╚═╝
</pre>

**(*≧▽≦) AI 기반 암호화폐 선물 거래 엔진**

*AI를 당신의 거래 파트너로, 시장 기회를 포착하세요*

<br/>

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg?style=flat-square)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B.svg?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![OKX](https://img.shields.io/badge/OKX-Supported-000000.svg?style=flat-square)](https://www.okx.com/)

<br/>

[中文文档](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [빠른 시작](#빠른-시작) | [AI 모델](#지원-ai-모델)

</div>

<br/>

---

## 면책 조항

**이 프로젝트는 교육 및 연구 목적으로만 제공됩니다. 투자 조언이 아닙니다.**

- 자동 거래에는 기술적 장애, API 오류, 네트워크 지연 등의 위험이 있습니다
- 과거 성과가 미래 결과를 보장하지 않습니다
- 잃어도 괜찮은 자금으로만 거래하세요
- 저자는 거래 손실에 대해 책임지지 않습니다

**이 소프트웨어를 사용함으로써 이러한 위험을 인지하고 수락한 것으로 간주됩니다.**

---

## 기능

### (￣▽￣) AI 기반 거래
- **12개 이상의 AI 제공업체** - DeepSeek, Qwen 3, GPT-5, Claude 4.5, Gemini 3 등
- **AI 아레나** - 여러 AI 모델이 동시 분석, 투표 기반 의사결정
- **5가지 거래 페르소나** - 헌터/밸런스/몽크/플래시/서퍼 스타일
- **커스텀 프롬프트** - AI 페르소나와 거래 전략 완전 커스터마이징 가능
- **스마트 뉴스 분석** - AI가 시장 뉴스를 해석하고 거래 신호 생성

### (◎_◎) 기술적 분석
- **멀티 타임프레임** - 1m/5m/15m/1h/4h/1d 분석 지원
- **풍부한 지표** - MA/EMA/RSI/MACD/KDJ/BOLL/ATR/OBV/VWAP 등
- **변화 추적** - 지표 트렌드 시각화
- **듀얼 채널 신호** - 멀티 타임프레임 신호 확인

### (￥ω￥) 거래 기능
- **OKX 선물** - OKX 무기한 계약 API와 깊은 통합
- **페이퍼 트레이딩** - 위험 없이 전략 테스트
- **리스크 관리** - 손절, 익절, 포지션 사이징, 일일 손실 한도
- **멀티 전략** - 내장 전략 + 커스텀 전략 개발
- **다른 거래소** - Binance, Bybit 지원 예정

---

## 완전한 거래 기능

### 지원 자산
BTC, ETH, SOL, BNB, XRP, DOGE, GT, TRUMP, ADA, WLFI 등 주요 암호화폐. 거래 풀은 인터페이스에서 완전히 설정 가능.

### 계약 유형
- **USDT 무기한 계약** - USDT로 정산
- **헤지 모드** - 롱과 숏 동시 보유 지원

### 마진 모드
| 모드 | 설명 | 사용 사례 |
|------|------|----------|
| 교차 | 모든 포지션이 마진 공유, 리스크도 공유 | 자본 효율성 높음, 경험 많은 트레이더용 |
| 격리 | 각 포지션이 독립적인 마진 보유 | 단일 포지션 청산이 다른 포지션에 영향 없음, 리스크 관리에 우수 |

### 레버리지 범위
- **설정 가능 범위**: 1x ~ 50x (UI에서 조정 가능)
- **권장**: 5x ~ 20x (리스크와 수익의 균형)
- **자동 디레버리지**: 고급 전략이 ATR 변동성에 따라 자동 조정

### 주문 유형
| 유형 | 설명 | 상태 |
|------|------|------|
| 시장가 주문 | 현재 가격으로 즉시 체결 | ✅ 지원됨 |
| 손절 | 가격 트리거 시 자동 청산 | ✅ 지원됨 |
| 익절 | 수익 목표 달성 시 자동 청산 | ✅ 지원됨 |
| 지정가 주문 | 지정 가격에서 대기 주문 | 🔜 곧 지원 |

### 리스크 관리 시스템
- **주문 크기 제한**: 단일 주문의 최대 금액
- **최대 포지션**: 총 포지션을 자산의 비율로 제한
- **일일 손실 한도**: 일일 손실 임계값 도달 시 자동 거래 중지
- **쿨다운 기간**: 손절 후 같은 방향 진입 방지

---

## 실시간 모니터링

### 웹 대시보드
- **계정 개요**: 자산, 사용 가능 잔액, 사용 마진
- **포지션 모니터**: 실시간 PnL, 레버리지, 청산 가격
- **차트**: 기술 지표가 포함된 멀티 타임프레임 캔들스틱

### AI 의사결정 로그
- **추론 과정**: AI 분석의 투명한 표시
- **신뢰도 점수**: 각 결정의 퍼센트 신뢰도
- **이력 검토**: 과거 결정 정확도 추적

### 거래 이력
- **완전한 기록**: 모든 진입, 청산, 손절, 익절 이벤트
- **타임스탬프**: 밀리초 정밀도의 거래 시간
- **통계**: 승률, 수익 팩터, 최대 드로다운 자동 계산

### (°∀°) 시장 센티먼트
- **Fear & Greed 지수** - 실시간 시장 센티먼트 모니터링
- **롱/숏 비율** - 시장 포지셔닝의 스마트 해석
- **온체인 데이터** - 고래 움직임, 거래소 유입/유출

### (｡･ω･｡) 사용자 인터페이스
- **Web UI** - 모던한 Streamlit 기반 대시보드
- **실시간 모니터링** - 라이브 포지션, PnL, 신호
- **원클릭 배포** - Docker 지원, Windows/Linux/macOS

---

## 빠른 시작

### 옵션 1: 로컬 설치

**Windows:**
```bash
git clone https://github.com/hey345437-boop/my-trading-bot-2.git
cd my-trading-bot-2
install.bat
```
설치 후 `启动机器人.bat`를 실행하고 웹 인터페이스에서 API 키를 설정하세요.

**Linux/macOS:**
```bash
git clone https://github.com/hey345437-boop/my-trading-bot-2.git
cd my-trading-bot-2
chmod +x install.sh && ./install.sh
source .venv/bin/activate && streamlit run app.py
```
http://localhost:8501 에 접속하여 인터페이스에서 API 키를 설정하세요.

### 옵션 2: Docker

```bash
git clone https://github.com/hey345437-boop/my-trading-bot-2.git
cd my-trading-bot-2
docker-compose up -d
```
http://localhost:8501 에 접속하여 인터페이스에서 API 키를 설정하세요.

---

## 설정

모든 설정은 웹 인터페이스에서 할 수 있습니다:

- **OKX API** - "거래 설정"에서 거래소 API 설정
- **AI API** - "AI 설정"에서 AI 제공업체 API 키 설정
- **거래 파라미터** - 인터페이스에서 거래 쌍, 레버리지, 포지션 크기 설정

> (・ω・) 고급 사용자는 Docker 배포를 위해 `.env` 파일로도 설정 가능

---

## 프로젝트 구조

```
hyweishi/
├── app.py                 # 메인 엔트리
├── ai/                    # AI 의사결정 엔진
├── core/                  # 코어 거래 엔진
├── database/              # 데이터베이스 레이어
├── exchange_adapters/     # 거래소 어댑터
├── strategies/            # 거래 전략
├── sentiment/             # 시장 센티먼트 분석
├── ui/                    # Web UI
└── utils/                 # 유틸리티
```

---

## 지원 AI 모델

| 제공업체 | 모델 | 무료 티어 | 비고 |
|----------|------|-----------|------|
| DeepSeek | V3.1 Chat, R1 Reasoner | ✅ | 고성능, 추천 |
| Qwen | Qwen 3 (235B), QwQ Plus | ✅ | Alibaba Cloud, 깊은 추론 |
| Spark | Spark 4.0 Ultra | ✅ Lite | iFlytek |
| Hunyuan | Turbo Latest | ✅ Lite | Tencent, 256K 컨텍스트 |
| Doubao | 1.5 Pro, Seed 1.6 | ✅ | ByteDance |
| GLM | GLM-4.6, GLM-4 Plus | ✅ Flash | Zhipu AI |
| OpenAI | GPT-5.2, o3, o4-mini | ❌ | 최신 플래그십 |
| Claude | Claude 4.5 Sonnet/Opus | ❌ | Anthropic |
| Gemini | Gemini 3 Pro, 2.5 Flash | ✅ | Google |
| Grok | Grok 4, Grok 3 | ❌ | xAI |
| Perplexity | Sonar Pro, Reasoning | ❌ | 웹 검색 기능 |

---

## 라이선스

이 프로젝트는 [AGPL-3.0](LICENSE) 라이선스 하에 배포됩니다.

**이것은 다음을 의미합니다:**
- ✅ 자유롭게 사용, 수정, 배포 가능
- ✅ 개인 학습 및 연구에 사용 가능
- ⚠️ 수정된 코드도 오픈소스로 공개해야 함
- ⚠️ 네트워크 서비스에 사용할 경우 소스 코드를 공개해야 함
- ❌ 저작권 표시와 라이선스 정보를 삭제하면 안 됨

**상업적 사용에 대해서는 저자에게 라이선스 문의를 해주세요.**

---

## 프로젝트 지원

이 프로젝트가 도움이 되었다면, 저자에게 커피 한 잔 사주세요 (´▽`ʃ♡ƪ)

**암호화폐 기부:**
- USDT (BEP20): `0x67c77a43d6524994af9497b4cd32080b95f2ace9`

---

## 연락처

- Email: hey345437@gmail.com
- QQ: 3269180865

---

## ⭐ 스타를 눌러주세요

<div align="center">

이 프로젝트가 도움이 되었다면, **Star** ⭐ 를 눌러주세요!

학생 개발자인 저에게 큰 힘이 됩니다 (´;ω;`)

여러분의 지원이 계속 개선해 나갈 동기가 됩니다!

[![GitHub stars](https://img.shields.io/github/stars/hey345437-boop/my-trading-bot-2?style=social)](https://github.com/hey345437-boop/my-trading-bot-2)

</div>
