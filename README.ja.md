# (・ω・) HyWeiShi (何以为势)

<div align="center">

<img src="https://img.shields.io/badge/AI-Powered-blueviolet?style=for-the-badge&logo=openai&logoColor=white" alt="AI Powered"/>
<img src="https://img.shields.io/badge/Crypto-Futures-orange?style=for-the-badge&logo=bitcoin&logoColor=white" alt="Crypto Futures"/>
<img src="https://img.shields.io/badge/Trading-Bot-success?style=for-the-badge&logo=robot&logoColor=white" alt="Trading Bot"/>

<br/><br/>

<pre>
██�? ██╗██╗   ██╗██╗    ██╗███████╗██╗███████╗██�? ██╗██╗
██�? ██║╚██�?██╔╝██�?   ██║██╔════╝██║██╔════╝██�? ██║██║
███████║ ╚████╔�?██�?█╗ ██║█████�? ██║███████╗███████║██║
██╔══██║  ╚██╔�? ██║███╗██║██╔══╝  ██║╚════██║██╔══██║██║
██�? ██�?  ██�?  ╚███╔███╔╝███████╗██║███████║██║  ██║██║
╚═�? ╚═�?  ╚═�?   ╚══╝╚══╝ ╚══════╝╚═╝╚══════╝╚═╝  ╚═╝╚═╝
</pre>

**(*≧▽�? AI搭載 暗号資産先物取引エンジン**

*AIをあなたの取引パートナーに、市場のチャンスを掴もう*

<br/>

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg?style=flat-square)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B.svg?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![OKX](https://img.shields.io/badge/OKX-Supported-000000.svg?style=flat-square)](https://www.okx.com/)

<br/>

[中文文档](README.md) | [English](README.en.md) | [한국어](README.ko.md) | [クイックスタート](#クイックスタート) | [AIモデル](#対応aiモデ�?

</div>

<br/>

---

## 免責事項

**本プロジェクトは教育・研究目的のみです。投資アドバイスではありません�?*

- 自動取引には技術的障害、APIエラー、ネットワーク遅延などのリスクがあります
- 過去のパフォーマンスは将来の結果を保証するものではありません
- 失っても問題ない資金のみで取引してくださ�?
- 作者は取引損失について一切責任を負いませ�?

**本ソフトウェアを使用することで、これらのリスクを認識し受け入れたものとみなします�?*

---

## 機能

### (￣▽�? AI搭載取引
- **12以上のAIプロバイダ�?* - DeepSeek、Qwen 3、GPT-5、Claude 4.5、Gemini 3など
- **AIアリーナ** - 複数のAIモデルが同時分析、投票ベースの意思決�?
- **5つの取引ペルソナ** - ハンター/バランス/モン�?フラッシ�?サーファースタイ�?
- **カスタムプロンプ�?* - AIペルソナと取引戦略を完全カスタマイズ可能
- **スマートニュース分析** - AIが市場ニュースを解釈し取引シグナルを生成

### (◎_�? テクニカル分�?
- **マルチタイムフレーム** - 1m/5m/15m/1h/4h/1d分析対応
- **豊富なインジケーター** - MA/EMA/RSI/MACD/KDJ/BOLL/ATR/OBV/VWAPなど
- **変化追跡** - インジケーターのトレンドを可視化
- **デュアルチャネルシグナル** - マルチタイムフレームシグナル確認

### (￥ω￥) 取引機能
- **OKX先物** - OKX無期限契約APIと深く統�?
- **ペーパートレード** - リスクなしで戦略テス�?
- **リスク管�?* - ストップロス、テイクプロフィット、ポジションサイジング、日次損失制�?
- **マルチ戦�?* - 内蔵戦略 + カスタム戦略開発
- **他の取引所** - Binance、Bybit対応予定

---

## 完全な取引機�?

### 対応資産
BTC、ETH、SOL、BNB、XRP、DOGE、GT、TRUMP、ADA、WLFIなどの主要暗号資産。取引プールはインターフェースで完全に設定可能�?

### 契約タイ�?
- **USDT無期限契�?* - USDTで決�?
- **ヘッジモード** - ロングとショートの同時保有をサポート

### 証拠金モード
| モー�?| 説明 | ユースケース |
|--------|------|--------------|
| クロ�?| 全ポジションで証拠金を共有、リスクも共�?| 資本効率が高い、経験豊富なトレーダー向�?|
| 分離 | 各ポジションが独立した証拠金を持�?| 単一ポジションの清算が他に影響しない、リスク管理に優れる |

### レバレッジ範�?
- **設定可能範囲**: 1x �?50x（UIで調整可能）
- **推奨**: 5x �?20x（リスクとリターンのバランス�?
- **自動デレバレッジ**: 高度な戦略がATRボラティリティに基づいて自動調整

### 注文タイ�?
| タイ�?| 説明 | ステータ�?|
|--------|------|------------|
| 成行注文 | 現在価格で即時執�?| �?対応済み |
| ストップロス | 価格トリガーで自動決�?| �?対応済み |
| テイクプロフィッ�?| 利益目標達成で自動決�?| �?対応済み |
| 指値注�?| 指定価格での待機注文 | 🔜 近日対応 |

### リスク管理システ�?
- **注文サイズ制�?*: 1回の注文の最大金�?
- **最大ポジション**: 総ポジションを資産の割合で制�?
- **日次損失制限**: 日次損失閾値に達したら自動取引停止
- **クールダウン期間**: ストップロス後の同方向エントリーを防�?

---

## リアルタイムモニタリング

### Webダッシュボード
- **アカウント概�?*: 資産、利用可能残高、使用証拠金
- **ポジションモニタ�?*: リアルタイムPnL、レバレッジ、清算価�?
- **チャート**: テクニカルインジケーター付きマルチタイムフレームローソク�?

### AI意思決定ロ�?
- **推論プロセス**: AI分析の透明な表�?
- **信頼度スコア**: 各決定のパーセンテージ信頼度
- **履歴レビュー**: 過去の決定精度を追跡

### 取引履歴
- **完全な記�?*: すべてのエントリー、エグジット、ストップロス、テイクプロフィットイベント
- **タイムスタン�?*: ミリ秒精度の取引時間
- **統計**: 勝率、プロフィットファクター、最大ドローダウンを自動計�?

### (°∀°) 市場センチメント
- **Fear & Greed指数** - リアルタイム市場センチメントモニタリング
- **ロン�?ショート比率** - 市場ポジショニングのスマート解釈
- **オンチェーンデー�?* - クジラの動き、取引所への流入/流出

### (｡･ω･｡) ユーザーインターフェース
- **Web UI** - モダンなStreamlitベースのダッシュボード
- **リアルタイムモニタリング** - ライブポジション、PnL、シグナ�?
- **ワンクリックデプロイ** - Docker対応、Windows/Linux/macOS

---

## クイックスタート

### オプショ�?: ローカルインストール

**Windows:**
```bash
git clone https://github.com/hey345437-boop/AI---hyweishi.git
cd AI---hyweishi
install.bat
```
インストール後、`启动机器�?bat`を実行し、WebインターフェースでAPIキーを設定してください�?

**Linux/macOS:**
```bash
git clone https://github.com/hey345437-boop/AI---hyweishi.git
cd AI---hyweishi
chmod +x install.sh && ./install.sh
source .venv/bin/activate && streamlit run app.py
```
http://localhost:8501 にアクセスし、インターフェースでAPIキーを設定してください�?

### オプショ�?: Docker

```bash
git clone https://github.com/hey345437-boop/AI---hyweishi.git
cd AI---hyweishi
docker-compose up -d
```
http://localhost:8501 にアクセスし、インターフェースでAPIキーを設定してください�?

---

## 設定

すべての設定はWebインターフェースで行えます：

- **OKX API** - 「取引設定」で取引所APIを設�?
- **AI API** - 「AI設定」でAIプロバイダーのAPIキーを設�?
- **取引パラメー�?* - インターフェースで取引ペア、レバレッジ、ポジションサイズを設定

> (・ω・) 上級ユーザーはDockerデプロイ用に`.env`ファイルでも設定可能

---

## プロジェクト構�?

```
hyweishi/
├── app.py                 # メインエントリー
├── ai/                    # AI意思決定エンジ�?
├── core/                  # コア取引エンジン
├── database/              # データベース�?
├── exchange_adapters/     # 取引所アダプタ�?
├── strategies/            # 取引戦略
├── sentiment/             # 市場センチメント分析
├── ui/                    # Web UI
└── utils/                 # ユーティリテ�?
```

---

## 対応AIモデ�?

| プロバイダ�?| モデ�?| 無料�?| 備�?|
|--------------|--------|--------|------|
| DeepSeek | V3.1 Chat, R1 Reasoner | �?| 高性能、推�?|
| Qwen | Qwen 3 (235B), QwQ Plus | �?| Alibaba Cloud、深い推�?|
| Spark | Spark 4.0 Ultra | �?Lite | iFlytek |
| Hunyuan | Turbo Latest | �?Lite | Tencent�?56Kコンテキスト |
| Doubao | 1.5 Pro, Seed 1.6 | �?| ByteDance |
| GLM | GLM-4.6, GLM-4 Plus | �?Flash | Zhipu AI |
| OpenAI | GPT-5.2, o3, o4-mini | �?| 最新フラッグシップ |
| Claude | Claude 4.5 Sonnet/Opus | �?| Anthropic |
| Gemini | Gemini 3 Pro, 2.5 Flash | �?| Google |
| Grok | Grok 4, Grok 3 | �?| xAI |
| Perplexity | Sonar Pro, Reasoning | �?| Web検索機能 |

---

## ライセン�?

本プロジェクトは[AGPL-3.0](LICENSE)ライセンスの下で公開されています�?

**これは以下を意味します：**
- �?自由に使用、修正、配布可�?
- �?個人学習・研究に使用可能
- ⚠️ 修正したコードもオープンソースにする必要あり
- ⚠️ ネットワークサービスに使用する場合、ソースコードを公開する必要あり
- �?著作権表示とライセンス情報を削除してはいけな�?

**商用利用については、作者にライセンスについてお問い合わせください�?*

---

## プロジェクトをサポー�?

このプロジェクトが役に立ったら、作者にコーヒーをおごってくださ�?(´▽`ʃ♡�?

**暗号資産での寄付:**
- USDT (BEP20): `0x67c77a43d6524994af9497b4cd32080b95f2ace9`

---

## お問い合わせ

- Email: hey345437@gmail.com
- QQ: 3269180865

---

## �?スターをお願いします

<div align="center">

このプロジェクトが役に立ったら�?*Star** �?をお願いします！

学生開発者の私にとって、とても励みになりま�?(´;ω;`)

皆さんのサポートが改善を続けるモチベーションになります！

[![GitHub stars](https://img.shields.io/github/stars/hey345437-boop/AI---hyweishi?style=social)](https://github.com/hey345437-boop/AI---hyweishi)

</div>
