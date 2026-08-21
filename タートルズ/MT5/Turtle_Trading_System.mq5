//+------------------------------------------------------------------+
//|                                     Turtle_Trading_System.mq5     |
//|   タートルズ・トレーディングシステム インジケーター (MetaTrader 5) |
//|   リチャード・デニス「タートル流トレーディング規則」の            |
//|   N(ボラティリティ) / 20・55日ブレイクアウト /                    |
//|   0.5N毎ピラミッディング / 2Nストップ / 10・20日エグジット を再現。|
//|   発注は行わない(自動売買ではない)。シグナルと推奨ロットを表示。   |
//+------------------------------------------------------------------+
#property copyright "Turtle Trading System"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 19
#property indicator_plots   14

#property indicator_label1  "System1 20日高値"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrLime
#property indicator_style1  STYLE_SOLID
#property indicator_width1  1

#property indicator_label2  "System1 20日安値"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrRed
#property indicator_style2  STYLE_SOLID
#property indicator_width2  1

#property indicator_label3  "System2 55日高値"
#property indicator_type3   DRAW_LINE
#property indicator_color3  clrDodgerBlue
#property indicator_style3  STYLE_DOT
#property indicator_width3  1

#property indicator_label4  "System2 55日安値"
#property indicator_type4   DRAW_LINE
#property indicator_color4  clrOrange
#property indicator_style4  STYLE_DOT
#property indicator_width4  1

#property indicator_label5  "System1 ストップ"
#property indicator_type5   DRAW_LINE
#property indicator_color5  clrMagenta
#property indicator_style5  STYLE_SOLID
#property indicator_width5  2

#property indicator_label6  "System2 ストップ"
#property indicator_type6   DRAW_LINE
#property indicator_color6  clrPurple
#property indicator_style6  STYLE_SOLID
#property indicator_width6  2

#property indicator_label7  "System1 買い"
#property indicator_type7   DRAW_ARROW
#property indicator_color7  clrLime
#property indicator_width7  2
#property indicator_label8  "System1 売り"
#property indicator_type8   DRAW_ARROW
#property indicator_color8  clrRed
#property indicator_width8  2
#property indicator_label9  "System1 追加"
#property indicator_type9   DRAW_ARROW
#property indicator_color9  clrYellow
#property indicator_width9  1
#property indicator_label10 "System1 撤退"
#property indicator_type10  DRAW_ARROW
#property indicator_color10 clrGray
#property indicator_width10 1

#property indicator_label11 "System2 買い"
#property indicator_type11  DRAW_ARROW
#property indicator_color11 clrDodgerBlue
#property indicator_width11 2
#property indicator_label12 "System2 売り"
#property indicator_type12  DRAW_ARROW
#property indicator_color12 clrOrange
#property indicator_width12 2
#property indicator_label13 "System2 追加"
#property indicator_type13  DRAW_ARROW
#property indicator_color13 clrAqua
#property indicator_width13 1
#property indicator_label14 "System2 撤退"
#property indicator_type14  DRAW_ARROW
#property indicator_color14 clrGray
#property indicator_width14 1

// ============================== 入力 ==============================
input group "=== システム設定 ==="
input bool   InpUseSystem1          = true;   // System1 を使う(20日ブレイク/10日エグジット)
input bool   InpUseSystem2          = false;  // System2 を使う(55日ブレイク/20日エグジット)
input bool   InpWhipsawFilterSystem1= true;   // System1: 直前が勝ちなら次のブレイクをスキップ

input group "=== N (ボラティリティ) ==="
input int    InpNPeriod             = 20;     // Nの期間

input group "=== 資金管理 ==="
input bool   InpUseManualBalance    = true;      // 口座残高を手動指定する
input double InpManualBalance       = 100950.0;  // 手動指定残高(口座通貨)
input double InpRiskPerUnitPct      = 0.25;      // 1ユニットあたりリスク(%残高)
input int    InpMaxUnits            = 3;         // 最大ユニット数(1-4)
input double InpDailyLossLimit      = 1000.0;    // 1日の最大許容損失(参考表示のみ)

input group "=== 表示・アラート ==="
input bool   InpShowDashboard       = true;   // ダッシュボードを表示
input bool   InpEnableAlerts        = true;   // シグナル発生時にAlertを鳴らす

// ============================== バッファ ==============================
double BufUpper20[], BufLower20[], BufUpper55[], BufLower55[];
double BufS1Stop[], BufS2Stop[];
double BufS1Buy[], BufS1Sell[], BufS1Add[], BufS1Exit[];
double BufS2Buy[], BufS2Sell[], BufS2Add[], BufS2Exit[];
double BufN[], BufExitHigh10[], BufExitLow10[], BufExitHigh20[], BufExitLow20[];

// 直近アラート済みバー時刻(重複アラート防止用)
datetime g_lastAlertTime[8];

//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0,  BufUpper20,    INDICATOR_DATA);
   SetIndexBuffer(1,  BufLower20,    INDICATOR_DATA);
   SetIndexBuffer(2,  BufUpper55,    INDICATOR_DATA);
   SetIndexBuffer(3,  BufLower55,    INDICATOR_DATA);
   SetIndexBuffer(4,  BufS1Stop,     INDICATOR_DATA);
   SetIndexBuffer(5,  BufS2Stop,     INDICATOR_DATA);
   SetIndexBuffer(6,  BufS1Buy,      INDICATOR_DATA);
   SetIndexBuffer(7,  BufS1Sell,     INDICATOR_DATA);
   SetIndexBuffer(8,  BufS1Add,      INDICATOR_DATA);
   SetIndexBuffer(9,  BufS1Exit,     INDICATOR_DATA);
   SetIndexBuffer(10, BufS2Buy,      INDICATOR_DATA);
   SetIndexBuffer(11, BufS2Sell,     INDICATOR_DATA);
   SetIndexBuffer(12, BufS2Add,      INDICATOR_DATA);
   SetIndexBuffer(13, BufS2Exit,     INDICATOR_DATA);
   SetIndexBuffer(14, BufN,          INDICATOR_CALCULATIONS);
   SetIndexBuffer(15, BufExitHigh10, INDICATOR_CALCULATIONS);
   SetIndexBuffer(16, BufExitLow10,  INDICATOR_CALCULATIONS);
   SetIndexBuffer(17, BufExitHigh20, INDICATOR_CALCULATIONS);
   SetIndexBuffer(18, BufExitLow20,  INDICATOR_CALCULATIONS);

   PlotIndexSetInteger(6,  PLOT_ARROW, 233); // ▲
   PlotIndexSetInteger(7,  PLOT_ARROW, 234); // ▼
   PlotIndexSetInteger(8,  PLOT_ARROW, 159); // ・(追加)
   PlotIndexSetInteger(9,  PLOT_ARROW, 251); // ×(撤退)
   PlotIndexSetInteger(10, PLOT_ARROW, 233);
   PlotIndexSetInteger(11, PLOT_ARROW, 234);
   PlotIndexSetInteger(12, PLOT_ARROW, 159);
   PlotIndexSetInteger(13, PLOT_ARROW, 251);

   for(int p = 0; p < 14; p++)
      PlotIndexSetDouble(p, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   ArrayInitialize(g_lastAlertTime, 0);

   IndicatorSetString(INDICATOR_SHORTNAME, "タートルズ・トレーディングシステム");
   CreateDashboard();
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, "TTS_DASH_");
}

//+------------------------------------------------------------------+
//| 状態は全期間の履歴に依存する(勝敗フィルタ・ピラミッド段数など)ため|
//| 正確性を優先し、毎回全期間を先頭から再計算する。                  |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                 const int prev_calculated,
                 const datetime &time[],
                 const double &open[],
                 const double &high[],
                 const double &low[],
                 const double &close[],
                 const long &tick_volume[],
                 const long &volume[],
                 const int &spread[])
{
   int entryLen1 = 20, exitLen1 = 10, entryLen2 = 55, exitLen2 = 20;
   int lookbackMax = MathMax(InpUseSystem2 ? entryLen2 : 0, InpUseSystem1 ? entryLen1 : 20);
   int warmup = MathMax(InpNPeriod, lookbackMax) + 1;
   if(rates_total < warmup + 1)
      return(0);

   for(int p = 0; p < rates_total; p++)
   {
      BufUpper20[p] = EMPTY_VALUE; BufLower20[p] = EMPTY_VALUE;
      BufUpper55[p] = EMPTY_VALUE; BufLower55[p] = EMPTY_VALUE;
      BufS1Stop[p]  = EMPTY_VALUE; BufS2Stop[p]  = EMPTY_VALUE;
      BufS1Buy[p]   = EMPTY_VALUE; BufS1Sell[p]  = EMPTY_VALUE;
      BufS1Add[p]   = EMPTY_VALUE; BufS1Exit[p]  = EMPTY_VALUE;
      BufS2Buy[p]   = EMPTY_VALUE; BufS2Sell[p]  = EMPTY_VALUE;
      BufS2Add[p]   = EMPTY_VALUE; BufS2Exit[p]  = EMPTY_VALUE;
   }

   // ---- N (TrueRangeのWilder平滑化。ATRと同一の式) ----
   double sumTR = 0;
   for(int i = 1; i <= InpNPeriod; i++)
   {
      double tr = MathMax(high[i]-low[i], MathMax(MathAbs(high[i]-close[i-1]), MathAbs(low[i]-close[i-1])));
      sumTR += tr;
      BufN[i] = EMPTY_VALUE;
   }
   BufN[InpNPeriod] = sumTR / InpNPeriod;
   for(int i = InpNPeriod + 1; i < rates_total; i++)
   {
      double tr = MathMax(high[i]-low[i], MathMax(MathAbs(high[i]-close[i-1]), MathAbs(low[i]-close[i-1])));
      BufN[i] = (BufN[i-1] * (InpNPeriod - 1) + tr) / InpNPeriod;
   }

   // ---- チャネル(当日足を含めない過去N本) ----
   for(int i = 0; i < rates_total; i++)
   {
      BufExitHigh10[i] = EMPTY_VALUE; BufExitLow10[i] = EMPTY_VALUE;
      BufExitHigh20[i] = EMPTY_VALUE; BufExitLow20[i] = EMPTY_VALUE;
      if(i < entryLen1) continue;
      BufUpper20[i] = Highest(high, i-entryLen1, i-1);
      BufLower20[i] = Lowest(low,  i-entryLen1, i-1);
      if(i >= exitLen1)
      {
         BufExitHigh10[i] = Highest(high, i-exitLen1, i-1);
         BufExitLow10[i]  = Lowest(low,  i-exitLen1, i-1);
      }
      if(i >= entryLen2)
      {
         BufUpper55[i] = Highest(high, i-entryLen2, i-1);
         BufLower55[i] = Lowest(low,  i-entryLen2, i-1);
      }
      if(i >= exitLen2)
      {
         BufExitHigh20[i] = Highest(high, i-exitLen2, i-1);
         BufExitLow20[i]  = Lowest(low,  i-exitLen2, i-1);
      }
   }

   // ---- System1 状態機械 ----
   int    s1_pos = 0, s1_units = 0;
   double s1_entries[4]; ArrayInitialize(s1_entries, 0);
   double s1_stop = 0;
   string s1_lastResult = "";

   // ---- System2 状態機械 ----
   int    s2_pos = 0, s2_units = 0;
   double s2_entries[4]; ArrayInitialize(s2_entries, 0);
   double s2_stop = 0;

   for(int i = warmup; i < rates_total; i++)
   {
      double n = BufN[i];
      if(n == EMPTY_VALUE || n <= 0) continue;

      // -------- System1 --------
      if(InpUseSystem1 && BufUpper20[i] != EMPTY_VALUE)
      {
         if(s1_pos == 0)
         {
            bool canBuy  = (high[i] >= BufUpper20[i]) && (!InpWhipsawFilterSystem1 || s1_lastResult != "win");
            bool canSell = (low[i]  <= BufLower20[i]) && (!InpWhipsawFilterSystem1 || s1_lastResult != "win");
            if(canBuy)
            {
               s1_pos = 1; s1_units = 1; s1_entries[0] = BufUpper20[i];
               s1_stop = BufUpper20[i] - 2*n;
               BufS1Buy[i] = low[i];
            }
            else if(canSell)
            {
               s1_pos = -1; s1_units = 1; s1_entries[0] = BufLower20[i];
               s1_stop = BufLower20[i] + 2*n;
               BufS1Sell[i] = high[i];
            }
         }
         else if(s1_pos == 1)
         {
            double lastEntry = s1_entries[s1_units-1];
            double addLevel  = lastEntry + 0.5*n;
            if(s1_units < InpMaxUnits && high[i] >= addLevel)
            {
               s1_entries[s1_units] = addLevel; s1_units++;
               s1_stop = addLevel - 2*n;
               BufS1Add[i] = high[i];
            }
            if(BufExitLow10[i] != EMPTY_VALUE && (low[i] <= s1_stop || low[i] <= BufExitLow10[i]))
            {
               double exitPrice = MathMin(low[i], s1_stop);
               s1_lastResult = (exitPrice > s1_entries[0]) ? "win" : "loss";
               BufS1Exit[i] = low[i];
               s1_pos = 0; s1_units = 0; ArrayInitialize(s1_entries, 0); s1_stop = 0;
            }
         }
         else if(s1_pos == -1)
         {
            double lastEntry = s1_entries[s1_units-1];
            double addLevel  = lastEntry - 0.5*n;
            if(s1_units < InpMaxUnits && low[i] <= addLevel)
            {
               s1_entries[s1_units] = addLevel; s1_units++;
               s1_stop = addLevel + 2*n;
               BufS1Add[i] = low[i];
            }
            if(BufExitHigh10[i] != EMPTY_VALUE && (high[i] >= s1_stop || high[i] >= BufExitHigh10[i]))
            {
               double exitPrice = MathMax(high[i], s1_stop);
               s1_lastResult = (exitPrice < s1_entries[0]) ? "win" : "loss";
               BufS1Exit[i] = high[i];
               s1_pos = 0; s1_units = 0; ArrayInitialize(s1_entries, 0); s1_stop = 0;
            }
         }
         BufS1Stop[i] = (s1_pos != 0) ? s1_stop : EMPTY_VALUE;
      }

      // -------- System2 --------
      if(InpUseSystem2 && BufUpper55[i] != EMPTY_VALUE)
      {
         if(s2_pos == 0)
         {
            if(high[i] >= BufUpper55[i])
            {
               s2_pos = 1; s2_units = 1; s2_entries[0] = BufUpper55[i];
               s2_stop = BufUpper55[i] - 2*n;
               BufS2Buy[i] = low[i];
            }
            else if(low[i] <= BufLower55[i])
            {
               s2_pos = -1; s2_units = 1; s2_entries[0] = BufLower55[i];
               s2_stop = BufLower55[i] + 2*n;
               BufS2Sell[i] = high[i];
            }
         }
         else if(s2_pos == 1)
         {
            double lastEntry2 = s2_entries[s2_units-1];
            double addLevel2  = lastEntry2 + 0.5*n;
            if(s2_units < InpMaxUnits && high[i] >= addLevel2)
            {
               s2_entries[s2_units] = addLevel2; s2_units++;
               s2_stop = addLevel2 - 2*n;
               BufS2Add[i] = high[i];
            }
            if(BufExitLow20[i] != EMPTY_VALUE && (low[i] <= s2_stop || low[i] <= BufExitLow20[i]))
            {
               BufS2Exit[i] = low[i];
               s2_pos = 0; s2_units = 0; ArrayInitialize(s2_entries, 0); s2_stop = 0;
            }
         }
         else if(s2_pos == -1)
         {
            double lastEntry2 = s2_entries[s2_units-1];
            double addLevel2  = lastEntry2 - 0.5*n;
            if(s2_units < InpMaxUnits && low[i] <= addLevel2)
            {
               s2_entries[s2_units] = addLevel2; s2_units++;
               s2_stop = addLevel2 + 2*n;
               BufS2Add[i] = low[i];
            }
            if(BufExitHigh20[i] != EMPTY_VALUE && (high[i] >= s2_stop || high[i] >= BufExitHigh20[i]))
            {
               BufS2Exit[i] = high[i];
               s2_pos = 0; s2_units = 0; ArrayInitialize(s2_entries, 0); s2_stop = 0;
            }
         }
         BufS2Stop[i] = (s2_pos != 0) ? s2_stop : EMPTY_VALUE;
      }

      if(i == rates_total - 1)
      {
         UpdateDashboard(n, s1_pos, s1_units, s1_stop, s1_entries,
                          s2_pos, s2_units, s2_stop, s2_entries);
         if(InpEnableAlerts && i > 0)
            CheckAlerts(time[i]);
      }
   }

   return(rates_total);
}

//+------------------------------------------------------------------+
double Highest(const double &arr[], int from, int to)
{
   double v = arr[from];
   for(int k = from+1; k <= to; k++) if(arr[k] > v) v = arr[k];
   return v;
}
double Lowest(const double &arr[], int from, int to)
{
   double v = arr[from];
   for(int k = from+1; k <= to; k++) if(arr[k] < v) v = arr[k];
   return v;
}

//+------------------------------------------------------------------+
void CheckAlerts(datetime barTime)
{
   double vals[8];
   int idx = ArraySize(BufS1Buy) - 1;
   vals[0]=BufS1Buy[idx]; vals[1]=BufS1Sell[idx]; vals[2]=BufS1Add[idx]; vals[3]=BufS1Exit[idx];
   vals[4]=BufS2Buy[idx]; vals[5]=BufS2Sell[idx]; vals[6]=BufS2Add[idx]; vals[7]=BufS2Exit[idx];
   string msgs[8] = {
      "System1: 20日高値ブレイクで買いシグナル",
      "System1: 20日安値ブレイクで売りシグナル",
      "System1: 0.5N到達でユニット追加",
      "System1: ストップまたは10日逆抜けで撤退",
      "System2: 55日高値ブレイクで買いシグナル",
      "System2: 55日安値ブレイクで売りシグナル",
      "System2: 0.5N到達でユニット追加",
      "System2: ストップまたは20日逆抜けで撤退"
   };
   for(int k = 0; k < 8; k++)
   {
      if(vals[k] != EMPTY_VALUE && g_lastAlertTime[k] != barTime)
      {
         g_lastAlertTime[k] = barTime;
         Alert(_Symbol, " ", EnumToString((ENUM_TIMEFRAMES)_Period), " タートルズ ", msgs[k]);
      }
   }
}

//+------------------------------------------------------------------+
void CreateDashboard()
{
   if(!InpShowDashboard) return;
   for(int i = 0; i < 12; i++)
   {
      string name = "TTS_DASH_" + IntegerToString(i);
      if(ObjectFind(0, name) < 0)
         ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_RIGHT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 10);
      ObjectSetInteger(0, name, OBJPROP_YDISTANCE, 20 + i*16);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clrWhite);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 8);
      ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
   }
}

//+------------------------------------------------------------------+
void UpdateDashboard(double n,
                      int s1_pos, int s1_units, double s1_stop, double &s1_entries[],
                      int s2_pos, int s2_units, double s2_stop, double &s2_entries[])
{
   if(!InpShowDashboard) return;

   double balance = InpUseManualBalance ? InpManualBalance : AccountInfoDouble(ACCOUNT_BALANCE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double valuePerPriceUnit = (tickSize > 0) ? tickValue / tickSize : 0;
   double riskAmount = balance * InpRiskPerUnitPct / 100.0;
   double suggestedLots = (n > 0 && valuePerPriceUnit > 0) ? riskAmount / (n * valuePerPriceUnit) : 0;

   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if(lotStep > 0) suggestedLots = MathFloor(suggestedLots / lotStep) * lotStep;
   if(suggestedLots < lotMin) suggestedLots = lotMin;

   string posText1 = (s1_pos==1) ? "ロング" : (s1_pos==-1) ? "ショート" : "ノーポジ";
   string posText2 = (s2_pos==1) ? "ロング" : (s2_pos==-1) ? "ショート" : "ノーポジ";
   double nextAdd1 = (s1_pos!=0) ? s1_entries[s1_units-1] + (s1_pos==1?0.5:-0.5)*n : 0;
   double nextAdd2 = (s2_pos!=0) ? s2_entries[s2_units-1] + (s2_pos==1?0.5:-0.5)*n : 0;
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   SetLabel(0, "タートルズ ダッシュボード");
   SetLabel(1, "N (ATR" + IntegerToString(InpNPeriod) + "): " + DoubleToString(n, digits));
   SetLabel(2, "推奨ロット(次エントリー): " + DoubleToString(suggestedLots, 2));
   SetLabel(3, "1ユニット許容損失: " + DoubleToString(riskAmount, 2));
   SetLabel(4, "最大時の総リスク%: " + DoubleToString(InpRiskPerUnitPct*InpMaxUnits, 2) + "%");
   SetLabel(5, "1日の最大許容損失: " + DoubleToString(InpDailyLossLimit, 2));
   SetLabel(6, "System1: " + posText1 + " (" + IntegerToString(s1_units) + "u)");
   SetLabel(7, "  Stop: " + ((s1_pos!=0) ? DoubleToString(s1_stop, digits) : "-") +
                "  次追加: " + ((s1_pos!=0 && s1_units<InpMaxUnits) ? DoubleToString(nextAdd1, digits) : "-"));
   SetLabel(8, "System2: " + posText2 + " (" + IntegerToString(s2_units) + "u)");
   SetLabel(9, "  Stop: " + ((s2_pos!=0) ? DoubleToString(s2_stop, digits) : "-") +
                "  次追加: " + ((s2_pos!=0 && s2_units<InpMaxUnits) ? DoubleToString(nextAdd2, digits) : "-"));
   SetLabel(10, "残高: " + DoubleToString(balance, 2) + (InpUseManualBalance ? " (手動)" : " (自動)"));
   SetLabel(11, "");
}

void SetLabel(int i, string text)
{
   string name = "TTS_DASH_" + IntegerToString(i);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
}
//+------------------------------------------------------------------+
