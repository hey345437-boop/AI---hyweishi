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

**(*≧▽≦) AI搭載 暗号資産先物取引エンジン**

*AIをあなたの取引パートナーに、市場のチャンスを掴もう*

<br/>

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg?style=flat-square)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B.svg?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![OKX](https://img.shields.io/badge/OKX-Supported-000000.svg?style=flat-square)](https://www.okx.com/)

<br/>

[中文文档](README.md) | [English](README.en.md) | [한국어](README.ko.md) | [クイックスタート](#クイックスタート) | [AIモデル](#対応aiモデル)

</div>

<br/>

---

## 免責事項

**本プロジェクトは教育・研究目的のみです。投資アドバイスではありません。**

- 自動取引には技術的障害、APIエラー、ネットワーク遅延などのリスクがあります
- 過去のパフォーマンスは将来の結果を保証するものではありません
- 失っても問題ない資金のみで取引してください
- 作者は取引損失について一切責任を負いません

**本ソフトウェアを使用することで、これらのリスクを認識し受け入れたものとみなします。**

---

## 機能

### (￣▽￣) AI搭載取引
- **12以上のAIプロバイダー** - DeepSeek、Qwen 3、GPT-5、Claude 4.5、Gemini 3など
- **AIアリーナ** - 複数のAIモデルが同時分析、投票ベースの意思決定
- **5つの取引ペルソナ** - ハンター/バランス/モンク/フラッシュ/サーファースタイル
- **カスタムプロンプト** - AIペルソナと取引戦略を完全カスタマイズ可能
- **スマートニュース分析** - AIが市場ニュースを解釈し取引シグナルを生成

### (◎_◎) テクニカル分析
- **マルチタイムフレーム** - 1m/5m/15m/1h/4h/1d分析対応
- **豊富なインジケーター** - MA/EMA/RSI/MACD/KDJ/BOLL/ATR/OBV/VWAPなど
- **変化追跡** - インジケーターのトレンドを可視化
- **デュアルチャネルシグナル** - マルチタイムフレームシグナル確認

### (￥ω￥) 取引機能
- **OKX先物** - OKX無期限契約APIと深く統合
- **ペーパートレード** - リスクなしで戦略テスト
- **リスク管理** - ストップロス、テイクプロフィット、ポジションサイジング、日次損失制限
- **マルチ戦略** - 内蔵戦略 + カスタム戦略開発
- **他の取引所** - Binance、Bybit対応予定

---

## 完全な取引機能

### 対応資産
BTC、ETH、SOL、BNB、XRP、DOGE、GT、TRUMP、ADA、WLFIなどの主要暗号資産。取引プールはインターフェースで完全に設定可能。

### 契約タイプ
- **USDT無期限契約** - USDTで決済
- **ヘッジモード** - ロングとショートの同時保有をサポート

### 証拠金モード
| モード | 説明 | ユースケース |
|--------|------|--------------|
| クロス | 全ポジションで証拠金を共有、リスクも共有 | 資本効率が高い、経験豊富なトレーダー向け |
| 分離 | 各ポジションが独立した証拠金を持つ | 単一ポジションの清算が他に影響しない、リスク管理に優れる |

### レバレッジ範囲
- **設定可能範囲**: 1x ～ 50x（UIで調整可能）
- **推奨**: 5x ～ 20x（リスクとリターンのバランス）
- **自動デレバレッジ**: 高度な戦略がATRボラティリティに基づいて自動調整

### 注文タイプ
| タイプ | 説明 | ステータス |
|--------|------|------------|
| 成行注文 | 現在価格で即時執行 | ✅ 対応済み |
| ストップロス | 価格トリガーで自動決済 | ✅ 対応済み |
| テイクプロフィット | 利益目標達成で自動決済 | ✅ 対応済み |
| 指値注文 | 指定価格での待機注文 | 🔜 近日対応 |

### リスク管理システム
- **注文サイズ制限**: 1回の注文の最大金額
- **最大ポジション**: 総ポジションを資産の割合で制限
- **日次損失制限**: 日次損失閾値に達したら自動取引停止
- **クールダウン期間**: ストップロス後の同方向エントリーを防止

---

## リアルタイムモニタリング

### Webダッシュボード
- **アカウント概要**: 資産、利用可能残高、使用証拠金
- **ポジションモニター**: リアルタイムPnL、レバレッジ、清算価格
- **チャート**: テクニカルインジケーター付きマルチタイムフレームローソク足

### AI意思決定ログ
- **推論プロセス**: AI分析の透明な表示
- **信頼度スコア**: 各決定のパーセンテージ信頼度
- **履歴レビュー**: 過去の決定精度を追跡

### 取引履歴
- **完全な記録**: すべてのエントリー、エグジット、ストップロス、テイクプロフィットイベント
- **タイムスタンプ**: ミリ秒精度の取引時間
- **統計**: 勝率、プロフィットファクター、最大ドローダウンを自動計算

### (°∀°) 市場センチメント
- **Fear & Greed指数** - リアルタイム市場センチメントモニタリング
- **ロング/ショート比率** - 市場ポジショニングのスマート解釈
- **オンチェーンデータ** - クジラの動き、取引所への流入/流出

### (｡･ω･｡) ユーザーインターフェース
- **Web UI** - モダンなStreamlitベースのダッシュボード
- **リアルタイムモニタリング** - ライブポジション、PnL、シグナル
- **ワンクリックデプロイ** - Docker対応、Windows/Linux/macOS

---

## クイックスタート

### オプション1: ローカルインストール

**Windows:**
```bash
git clone https://github.com/hey345437-boop/my-trading-bot-2.git
cd my-trading-bot-2
install.bat
```
インストール後、`启动机器人.bat`を実行し、WebインターフェースでAPIキーを設定してください。

**Linux/macOS:**
```bash
git clone https://github.com/hey345437-boop/my-trading-bot-2.git
cd my-trading-bot-2
chmod +x install.sh && ./install.sh
source .venv/bin/activate && streamlit run app.py
```
http://localhost:8501 にアクセスし、インターフェースでAPIキーを設定してください。

### オプション2: Docker

```bash
git clone https://github.com/hey345437-boop/my-trading-bot-2.git
cd my-trading-bot-2
docker-compose up -d
```
http://localhost:8501 にアクセスし、インターフェースでAPIキーを設定してください。

---

## 設定

すべての設定はWebインターフェースで行えます：

- **OKX API** - 「取引設定」で取引所APIを設定
- **AI API** - 「AI設定」でAIプロバイダーのAPIキーを設定
- **取引パラメータ** - インターフェースで取引ペア、レバレッジ、ポジションサイズを設定

> (・ω・) 上級ユーザーはDockerデプロイ用に`.env`ファイルでも設定可能

---

## プロジェクト構造

```
hyweishi/
├── app.py                 # メインエントリー
├── ai/                    # AI意思決定エンジン
├── core/                  # コア取引エンジン
├── database/              # データベース層
├── exchange_adapters/     # 取引所アダプター
├── strategies/            # 取引戦略
├── sentiment/             # 市場センチメント分析
├── ui/                    # Web UI
└── utils/                 # ユーティリティ
```

---

## 対応AIモデル

| プロバイダー | モデル | 無料枠 | 備考 |
|--------------|--------|--------|------|
| DeepSeek | V3.1 Chat, R1 Reasoner | ✅ | 高性能、推奨 |
| Qwen | Qwen 3 (235B), QwQ Plus | ✅ | Alibaba Cloud、深い推論 |
| Spark | Spark 4.0 Ultra | ✅ Lite | iFlytek |
| Hunyuan | Turbo Latest | ✅ Lite | Tencent、256Kコンテキスト |
| Doubao | 1.5 Pro, Seed 1.6 | ✅ | ByteDance |
| GLM | GLM-4.6, GLM-4 Plus | ✅ Flash | Zhipu AI |
| OpenAI | GPT-5.2, o3, o4-mini | ❌ | 最新フラッグシップ |
| Claude | Claude 4.5 Sonnet/Opus | ❌ | Anthropic |
| Gemini | Gemini 3 Pro, 2.5 Flash | ✅ | Google |
| Grok | Grok 4, Grok 3 | ❌ | xAI |
| Perplexity | Sonar Pro, Reasoning | ❌ | Web検索機能 |

---

## ライセンス

本プロジェクトは[AGPL-3.0](LICENSE)ライセンスの下で公開されています。

**これは以下を意味します：**
- ✅ 自由に使用、修正、配布可能
- ✅ 個人学習・研究に使用可能
- ⚠️ 修正したコードもオープンソースにする必要あり
- ⚠️ ネットワークサービスに使用する場合、ソースコードを公開する必要あり
- ❌ 著作権表示とライセンス情報を削除してはいけない

**商用利用については、作者にライセンスについてお問い合わせください。**

---

## プロジェクトをサポート

このプロジェクトが役に立ったら、作者にコーヒーをおごってください (´▽`ʃ♡ƪ)

**暗号資産での寄付:**
- USDT (BEP20): `0x67c77a43d6524994af9497b4cd32080b95f2ace9`

---

## お問い合わせ

- Email: hey345437@gmail.com
- QQ: 3269180865

---

## ⭐ スターをお願いします

<div align="center">

このプロジェクトが役に立ったら、**Star** ⭐ をお願いします！

学生開発者の私にとって、とても励みになります (´;ω;`)

皆さんのサポートが改善を続けるモチベーションになります！

[![GitHub stars](https://img.shields.io/github/stars/hey345437-boop/my-trading-bot-2?style=social)](https://github.com/hey345437-boop/my-trading-bot-2)

</div>
