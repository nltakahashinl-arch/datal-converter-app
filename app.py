import streamlit as st
import pandas as pd
import io

# --- 1. アプリの設定と初期化 ---
st.set_page_config(page_title="データ変換アプリ(B2風)", layout="wide")

# セッション状態の初期化
if 'saved_rules' not in st.session_state:
    initial_df = pd.DataFrame({
        "No": range(1, 51),
        "項目名": [f"項目{i}" for i in range(1, 51)],
        "元列": [""] * 50,
        "処理": ["そのまま"] * 50,
        "引数1": [""] * 50
    })
    st.session_state['saved_rules'] = {"新規設定": initial_df}

# --- 2. 共通関数 ---
def read_csv_safe(file):
    try:
        return pd.read_csv(file)
    except UnicodeDecodeError:
        file.seek(0)
        return pd.read_csv(file, encoding='cp932')

def apply_rule(df_source, rule_df):
    result_data = {}
    for _, row in rule_df.iterrows():
        target_col_name = row['項目名']
        source_col_name = row['元列']
        action = row['処理']
        arg1 = row['引数1']
        
        if not target_col_name: continue

        if source_col_name in df_source.columns and action != "固定値":
            series = df_source[source_col_name].copy()
        else:
            series = pd.Series([""] * len(df_source))
        
        try:
            if action == "そのまま":
                result_data[target_col_name] = series
            elif action == "左から抽出":
                num = int(arg1) if arg1 else 0
                result_data[target_col_name] = series.astype(str).str[:num]
            elif action == "右から抽出":
                num = int(arg1) if arg1 else 0
                result_data[target_col_name] = series.astype(str).str[-num:]
            elif action == "日付変換(yyyymmdd)":
                result_data[target_col_name] = pd.to_datetime(series, errors='coerce').dt.strftime('%Y%m%d')
            elif action == "乗算":
                val = float(arg1) if arg1 else 1.0
                result_data[target_col_name] = pd.to_numeric(series, errors='coerce') * val
            elif action == "固定値":
                result_data[target_col_name] = arg1 
            else:
                result_data[target_col_name] = series 
        except:
            result_data[target_col_name] = pd.Series(["エラー"] * len(df_source))

    return pd.DataFrame(result_data)

# --- 3. メイン画面レイアウト ---
st.title("Excel/CSV 並び順変換アプリ")
mode = st.sidebar.radio("メニュー", ["変換実行", "型の管理・作成(操作盤)"])

# ==========================================
# モードA: 変換実行
# ==========================================
if mode == "変換実行":
    st.header("📂 データの変換実行")
    rule_names = list(st.session_state['saved_rules'].keys())
    
    selected_rule_name = st.selectbox("型を選択", rule_names)
    uploaded_file = st.file_uploader("請求データをアップロード", type=['xlsx', 'csv'])
    
    if uploaded_file and selected_rule_name:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_source = read_csv_safe(uploaded_file)
            else:
                df_source = pd.read_excel(uploaded_file)
                
            if st.button("変換実行", type="primary"):
                current_rule = st.session_state['saved_rules'][selected_rule_name]
                df_result = apply_rule(df_source, current_rule)
                
                st.success("変換完了！")
                st.dataframe(df_result.head())
                
                csv_str = df_result.to_csv(index=False)
                csv_data = csv_str.encode('utf-8-sig')
                
                st.download_button("CSVダウンロード", csv_data, "converted_data.csv", "text/csv")
        except Exception as e:
            st.error(f"ファイル読み込みエラー: {e}")

# ==========================================
# モードB: 型の管理・作成（画面分割版）
# ==========================================
elif mode == "型の管理・作成(操作盤)":
    
    # 1. 型の選択エリア（トップ配置）
    col_head1, col_head2, col_head3 = st.columns([2, 2, 3])
    with col_head1:
        edit_mode = st.radio("操作モード", ["既存編集", "新規作成"], horizontal=True)
    with col_head2:
        if edit_mode == "新規作成":
            target_rule_name = st.text_input("型名を入力", "B社用設定")
            if target_rule_name not in st.session_state['saved_rules']:
                st.session_state['saved_rules'][target_rule_name] = pd.DataFrame({
                    "No": range(1, 51),
                    "項目名": [f"項目{i}" for i in range(1, 51)],
                    "元列": [""] * 50,
                    "処理": ["そのまま"] * 50,
                    "引数1": [""] * 50
                })
        else:
            rule_list = list(st.session_state['saved_rules'].keys())
            target_rule_name = st.selectbox("編集する型", rule_list)

    # 編集中のデータを取得
    current_df = st.session_state['saved_rules'][target_rule_name]
    
    # 2. サンプル読み込み（トップ配置）
    with col_head3:
        sample_file = st.file_uploader("サンプル(Excel/CSV)読込", key="sample_v7")
        df_sample = None
        sample_options = ["(未選択)"]
        if sample_file:
            try:
                if sample_file.name.endswith('.csv'):
                    df_sample = read_csv_safe(sample_file)
                else:
                    df_sample = pd.read_excel(sample_file)
                
                # プルダウン用のリスト作成
                first_row = df_sample.iloc[0]
                for col in df_sample.columns:
                    val = str(first_row[col])
                    if len(val) > 10: val = val[:10] + "..."
                    sample_options.append(f"{col} （例: {val}）")
            except:
                st.error("読込エラー")

    st.markdown("---")

    # ★レイアウト変更: 左側（操作パネル）と 右側（結果テーブル）に分割
    col_control, col_table = st.columns([1, 2])

    # === 左側：操作パネル ===
    with col_control:
        st.subheader("🎮 操作パネル")
        st.info("ここで項目を選んで紐付けます")
        
        # ① 出力項目の選択（プルダウン化で省スペース）
        target_items = current_df["項目名"].tolist()
        # フォーマット: "1. 項目名" のように表示
        target_idx = st.selectbox(
            "① 出力項目を選んでください", 
            range(len(target_items)), 
            format_func=lambda x: f"{x+1}. {target_items[x]}"
        )
        
        # ② 元データの選択
        source_col_str = st.selectbox("② 割り当てるデータを選んでください", sample_options)
        
        # ③ ボタンエリア
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("紐付け実行 👇", use_container_width=True, type="primary"):
                if source_col_str != "(未選択)":
                    real_col_name = source_col_str.split(" （例:")[0]
                    current_df.at[target_idx, "元列"] = real_col_name
                    st.session_state['saved_rules'][target_rule_name] = current_df
                    st.success(f"No.{target_idx+1} に設定しました")
                else:
                    st.warning("データを選んでください")
        
        with col_btn2:
            if st.button("クリア ✕", use_container_width=True):
                current_df.at[target_idx, "元列"] = ""
                st.session_state['saved_rules'][target_rule_name] = current_df
                st.info(f"No.{target_idx+1} をクリアしました")
        
        st.caption("※紐付け後、右側の表が自動更新されます。")

    # === 右側：結果テーブル ===
    with col_table:
        st.subheader("📋 設定一覧（プレビュー）")
        # 編集可能なテーブルを常に表示（高さ調整済み）
        edited_df = st.data_editor(
            current_df,
            height=600, # 高さを固定してスクロールしやすくする
            column_config={
                "No": st.column_config.NumberColumn(width="small"),
                "元列": st.column_config.TextColumn(width="medium"),
                "処理": st.column_config.SelectboxColumn(
                    "処理内容",
                    options=["そのまま", "左から抽出", "右から抽出", "日付変換(yyyymmdd)", "乗算", "固定値"],
                    width="medium"
                )
            },
            key="editor_v7"
        )
        
        # テーブルで直接編集された場合も保存
        if not edited_df.equals(current_df):
            st.session_state['saved_rules'][target_rule_name] = edited_df
