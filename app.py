import streamlit as st
import pandas as pd
import io

# --- 1. アプリの設定と初期化 ---
st.set_page_config(page_title="データ変換アプリ", layout="wide")

# セッション状態（メモリ内保存）の初期化
# 実際にはここでデータベースやJSONファイルから読み込みます
if 'saved_rules' not in st.session_state:
    st.session_state['saved_rules'] = {
        "デモ用_B社設定": pd.DataFrame([
            {"No": 1, "項目名": "請求日", "元列": "日付", "処理": "日付変換(yyyymmdd)", "引数1": ""},
            {"No": 2, "項目名": "顧客名", "元列": "氏名", "処理": "そのまま", "引数1": ""},
            {"No": 3, "項目名": "分類コード", "元列": "商品ID", "処理": "左から抽出", "引数1": "3"},
            {"No": 4, "項目名": "金額(税抜)", "元列": "単価", "処理": "乗算", "引数1": "10"}
        ])
    }

# --- 2. 変換ロジック（エンジン部分） ---
def apply_rule(df_source, rule_df):
    """
    元データ(df_source)に対して、ルール(rule_df)を適用し、
    新しいデータフレームを作成して返す関数
    """
    result_data = {}
    
    # ルールの1行ずつ処理
    for _, row in rule_df.iterrows():
        target_col_name = row['項目名']
        source_col_name = row['元列']
        action = row['処理']
        arg1 = row['引数1']
        
        # 元の列が存在しない場合のハンドリング（空文字を入れるなど）
        if source_col_name not in df_source.columns and action != "固定値":
            series = pd.Series([""] * len(df_source)) # 空の列
        else:
            if action != "固定値":
                series = df_source[source_col_name].copy()
        
        # --- ここで各処理を分岐 ---
        try:
            if action == "そのまま":
                result_data[target_col_name] = series
            
            elif action == "左から抽出":
                num = int(arg1)
                result_data[target_col_name] = series.astype(str).str[:num]
                
            elif action == "右から抽出":
                num = int(arg1)
                result_data[target_col_name] = series.astype(str).str[-num:]

            elif action == "日付変換(yyyymmdd)":
                result_data[target_col_name] = pd.to_datetime(series).dt.strftime('%Y%m%d')

            elif action == "乗算":
                val = float(arg1)
                result_data[target_col_name] = pd.to_numeric(series, errors='coerce') * val
                
            elif action == "固定値":
                result_data[target_col_name] = arg1  # 全行に同じ値

            else:
                result_data[target_col_name] = series # デフォルト
                
        except Exception as e:
            st.warning(f"列「{target_col_name}」の処理中にエラー: {e}")
            result_data[target_col_name] = series

    return pd.DataFrame(result_data)

# --- 3. メイン画面構成 ---
st.title("Excel/CSV 並び順変換アプリ")

# サイドバーでモード切替
mode = st.sidebar.radio("メニュー", ["変換実行", "型の管理・作成"])

# ==========================================
# モードA: 変換実行（日常業務）
# ==========================================
if mode == "変換実行":
    st.header("📂 データの変換実行")
    
    # 1. 型（ルール）の選択
    rule_names = list(st.session_state['saved_rules'].keys())
    selected_rule_name = st.selectbox("使用する型（仕入れ先）を選択してください", rule_names)
    
    # 2. ファイルアップロード
    uploaded_file = st.file_uploader("請求データをアップロード (Excel or CSV)", type=['xlsx', 'csv'])
    
    if uploaded_file and selected_rule_name:
        # データの読み込み
        if uploaded_file.name.endswith('.csv'):
            df_source = pd.read_csv(uploaded_file)
        else:
            df_source = pd.read_excel(uploaded_file)
            
        st.subheader("1. 元データプレビュー")
        st.dataframe(df_source.head())
        
        # 3. 変換実行ボタン
        if st.button("変換実行", type="primary"):
            # ルールの取得
            current_rule = st.session_state['saved_rules'][selected_rule_name]
            
            # 変換処理
            df_result = apply_rule(df_source, current_rule)
            
            st.subheader("2. 変換結果プレビュー")
            st.dataframe(df_result.head())
            
            # 4. ダウンロード
            # CSVとして出力（Excel出力も可能）
            csv_data = df_result.to_csv(index=False, encoding='utf-8_sig')
            st.download_button(
                label="変換結果をダウンロード (CSV)",
                data=csv_data,
                file_name="converted_data.csv",
                mime="text/csv"
            )

# ==========================================
# モードB: 型の管理・作成（管理者用）
# ==========================================
elif mode == "型の管理・作成":
    st.header("🛠 変換ルールの作成・編集")
    
    # 新規作成か既存編集か
    edit_mode = st.radio("操作", ["既存の型を編集", "新規作成"], horizontal=True)
    
    if edit_mode == "既存の型を編集":
        rule_list = list(st.session_state['saved_rules'].keys())
        if not rule_list:
            st.info("保存されている型がありません。新規作成してください。")
            target_rule_name = None
        else:
            target_rule_name = st.selectbox("編集する型を選択", rule_list)
            # 既存データのロード
            initial_data = st.session_state['saved_rules'][target_rule_name]
    else:
        target_rule_name = st.text_input("新しい型の名前（例: C社用設定）")
        # 空のデータフレームを用意
        initial_data = pd.DataFrame(
            [{"No": 1, "項目名": "列1", "元列": "", "処理": "そのまま", "引数1": ""}]
        )

    if target_rule_name:
        st.info("下の表を直接編集して、変換ルールを定義してください。（行の追加・削除が可能です）")
        
        # 編集可能なデータフレーム (Data Editor)
        edited_rule_df = st.data_editor(
            initial_data,
            num_rows="dynamic", # 行の追加削除を許可
            column_config={
                "処理": st.column_config.SelectboxColumn(
                    "処理内容",
                    options=[
                        "そのまま", 
                        "左から抽出", 
                        "右から抽出", 
                        "日付変換(yyyymmdd)", 
                        "乗算",
                        "固定値"
                    ],
                    required=True
                )
            },
            hide_index=True
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("設定を保存"):
                st.session_state['saved_rules'][target_rule_name] = edited_rule_df
                st.success(f"「{target_rule_name}」を保存しました！")
        
        # 将来的な機能のプレースホルダー
        st.markdown("---")
        st.markdown("※ ここに「Excel設定書からのインポート機能」を追加予定です。")
