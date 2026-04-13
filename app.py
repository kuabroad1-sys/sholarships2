import pandas as pd
import numpy as np

# 1. 예산 입력 (사용자가 직접 수정 가능)
TOTAL_BUDGET_LIMIT = 500000000  # 예: 5억 원

# 2. 데이터 로드
student_df = pd.read_csv('2.xlsx - Data.csv')
mapping_df = pd.read_csv('계열확인.xlsx - Sheet1.csv')
mapping_dict = mapping_df.set_index('대학').to_dict(orient='index')

# 3. 데이터 매핑 및 필터링
def get_info(college):
    info = mapping_dict.get(college, {'계열': '기타', '수업료': 0})
    return pd.Series([info['계열'], info['수업료']])

student_df[['계열', '수업료']] = student_df['대학'].apply(get_info)

# 필터링 조건 적용
eligible_df = student_df[
    (student_df['등록학기수'] < 8) &
    (student_df['포기전 최종학기 취득학점'] >= 12) &
    (student_df['국적'] != '대한민국') &
    (student_df['추천기관'] != '국립국제교육원') &
    (student_df['포기전 최종학기 평점평균'] >= 3.0)
].copy()

# 4. 등급별 인원 산출 (올림 처리)
T = len(eligible_df)
quotas = {
    '100%': (np.ceil(T / 65), 1.0),
    '60%': (np.ceil(T / 24), 0.6),
    '30%': (np.ceil(T / 20), 0.3),
    '10%': (np.ceil(T / 12), 0.1)
}

# 5. 계열별 비율 계산
group_ratios = eligible_df['계열'].value_counts() / T

# 6. 선발 로직 실행
final_list = []
for group in group_ratios.index:
    group_df = eligible_df[eligible_df['계열'] == group].sort_values(by='포기전 최종학기 평점평균', ascending=False)
    ratio = group_ratios[group]
    
    for grade, (total_q, rate) in quotas.items():
        g_quota = int(round(total_q * ratio))
        if g_quota == 0: continue
        
        temp_top = group_df.head(g_quota)
        if not temp_top.empty:
            cut_off_gpa = temp_top.iloc[-1]['포기전 최종학기 평점평균']
            selected = group_df[group_df['포기전 최종학기 평점평균'] >= cut_off_gpa].copy()
            selected = selected[~selected['학번'].isin([s['학번'] for s in final_list])]
            
            for _, row in selected.iterrows():
                student_data = row.to_dict()
                student_data['장학등급'] = grade
                student_data['수혜금액'] = int(row['수업료'] * rate)
                final_list.append(student_data)
            
            group_df = group_df[~group_df['학번'].isin(selected['학번'])]

# 7. 예산 검증 및 결과 보고
final_df = pd.DataFrame(final_list)
total_spent = final_df['수혜금액'].sum()

print("-" * 30)
print(f"입력된 제한 예산: {TOTAL_BUDGET_LIMIT:,}원")
print(f"실제 집행 예정액: {total_spent:,}원")

if total_spent > TOTAL_BUDGET_LIMIT:
    diff = total_spent - TOTAL_BUDGET_LIMIT
    print(f"⚠️ 경고: 예산이 {diff:,}원 초과되었습니다! 인원 조정이 필요합니다.")
else:
    print("✅ 예산 범위 내에 있습니다. 선발을 진행합니다.")
print("-" * 30)

final_df.to_excel('장학선발_최종결과_예산체크.xlsx', index=False)