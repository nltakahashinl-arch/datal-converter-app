import streamlit as st
import pandas as pd
import io

# --- 1. アプリの設定と初期化 ---
st.set_page_config(page_title="データ変換アプリ(B2風)", layout="wide")

# セッション状態の初期化
if 'saved_rules' not in st.session_state:
    # ★修正: 50行分の空枠を作成
    initial_df = pd.DataFrame({
        "No": range(1, 51),
        "項目名": [f"項目{i}" for i in range(1, 51)],
        "元列": [""] * 50,
        "処理": ["そのまま"] * 50,
        "引数1": [""] * 50
    })
    st.session_state['saved_rules'] = {"新規設定": initial_df}

# --- 2. 変換ロジック ---
def apply_rule(df_source, rule_df):
    result_data = {}
    
    for _, row in rule_df.iterrows():
        target_col_name = row['項目名']
        source_col_name = row['元列']
        action = row['処理']
        arg1 = row['引数1']
        
        # 項目名が空ならスキップ
        if not target_col_name:
            continue

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

# --- CSV読み込み用の関数 ---
def read_csv_safe(file):
    try:
        return pd.read_csv(file)
    except UnicodeDecodeError:
        file.seek(0)
        return pd.read_csv(file, encoding='cp932')

# --- 3. メイン画面 ---
st.title("Excel/CSV 並び順変換アプリ")
mode = st.sidebar.radio("メニュー", ["変換実行", "型の管理・作成(B2モード)"])

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
                
                # Excel用にBOM付きUTF-8にする
                csv_str = df_result.to_csv(index=False)
                csv_data = csv_str.encode('utf-8-sig')
                
                st.download_button(
                    label="CSVでダウンロード",
                    data=csv_data,
                    file_name="converted_data.csv",
                    mime="text/csv"
                )
        except Exception as e:
            st.error(f"ファイル読み込みエラー: {e}")

# ==========================================
# モードB: 型の管理・作成（B2風UI）
# ==========================================
elif mode == "型の管理・作成(B2モード)":
    st.header("🛠 紐付け設定 (B2ライク)")
    
    col_top1, col_top2 = st.columns([1, 1])
    with col_top1:
        edit_mode = st.radio("操作", ["既存編集", "新規作成"], horizontal=True)
    
    if edit_mode == "新規作成":
        target_rule_name = st.text_input("新しい型名", "B社用設定")
        if target_rule_name not in st.session_state['saved_rules']:
            # ★修正: ここも50行分作成
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

    current_df = st.session_state['saved_rules'][target_rule_name]

    st.markdown("---")

    st.info("Step 1: まずはサンプルデータを読み込んで、右側に表示させましょう")
    sample_file = st.file_uploader("サンプルファイル (Excel/CSV)", key="sample_b2")
    
    df_sample = None
    sample_options = []
    
    if sample_file:
        try:
            if sample_file.name.endswith('.csv'):
                df_sample = read_csv_safe(sample_file)
            else:
                df_sample = pd.read_excel(sample_file)
            
            first_row = df_sample.iloc[0]
            for col in df_sample.columns:
                val = str(first_row[col])
                if len(val) > 10: val = val[:10] + "..."
                sample_options.append(f"{col} （例: {val}）")
                
        except Exception as e:
            st.error(f"読み込みエラー詳細: {e}")

    st.markdown("---")
    st.subheader("Step 2: 紐付け作業")

    col_left, col_center, col_right = st.columns([2, 1, 2])

    with col_left:
        st.markdown("**① 出力したい項目 (レイアウト)**")
        target_items = current_df["項目名"].tolist()
        # 50項目あると長いので、スクロールして選んでください
        selected_target_index = st.radio("出力項目を選択", range(len(target_items)), format_func=lambda x: f"{x+1}. {target_items[x]}")

    with col_right:
        st.markdown("**② 取り込みデータの列 (データ抜粋)**")
        if df_sample is not None:
            selected_source_str = st.radio("割り当てる列を選択", sample_options)
            selected_source_col = selected_source_str.split(" （例:")[0]
        else:
            st.warning("ファイルをアップロードしてください")
            selected_source_col = None

    with col_center:
        st.write("") 
        st.write("") 
        st.write("") 
        if st.button("<< 紐付け (Link)"):
            if selected_source_col:
                current_df.at[selected_target_index, "元列"] = selected_source_col
                st.session_state['saved_rules'][target_rule_name] = current_df
                st.success(f"紐付け: {selected_source_col}")
            else:
                st.error("右側のデータを選んでください")

        if st.button("クリア"):
            current_df.at[selected_target_index, "元列"] = ""
            st.session_state['saved_rules'][target_rule_name] = current_df
            st.info("解除しました")

    st.markdown("---")
    st.subheader("Step 3: 設定の微調整と確認")
    
    edited_df = st.data_editor(
        current_df,
        num_rows="dynamic",
        column_config={
            "処理": st.column_config.SelectboxColumn(
                "処理内容",
                options=["そのまま", "左から抽出", "右から抽出", "日付変換(yyyymmdd)", "乗算", "固定値"]
            )
        },
        key="editor_b2"
    )
    
    if not edited_df.equals(current_df):
        st.session_state['saved_rules'][target_rule_name] = edited_df
