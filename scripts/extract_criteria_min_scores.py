from django_bootstrap import bootstrap
bootstrap()

import sys
import csv
import json
from datetime import datetime

from majors.models import AdmissionProject, AdmissionRound, Faculty
from criteria.models import AdmissionCriteria, COMPONENT_WEIGHT_TYPE_CHOICES

FIELDS = [
    'program_id',
    'major_id',
    'project_id',
    'project_name_th',
    'project_name_en',
    'type',
    'component_weight',
    'component_pat',
    'receive_student_number',
    'gender_male_number',
    'gender_female_number',
    'receive_add_limit',
    'join_id',
    'only_formal',
    'receive_student_number_formal ',
    'only_international',
    'receive_student_number_international ',
    'only_vocational',
    'receive_student_number_vocational',
    'only_non_formal',
    'receive_student_number_nonformal ',
    'min_height_male',
    'min_height_female',
    'min_weight_male',
    'min_weight_female',
    'max_weight_male',
    'max_weight_female',
    'min_hwr_male',
    'min_hwr_female',
    'min_bmi_male',
    'min_bmi_female',
    'max_bmi_male',
    'max_bmi_female',
    'min_r4_total_score',
    'min_gpax',
    'min_credit_gpa21',
    'min_credit_gpa22',
    'min_credit_gpa23',
    'min_credit_gpa24',
    'min_credit_gpa25',
    'min_credit_gpa26',
    'min_credit_gpa27',
    'min_credit_gpa28',
    'min_gpa21',
    'min_gpa22',
    'min_gpa23',
    'min_gpa24',
    'min_gpa25',
    'min_gpa26',
    'min_gpa27',
    'min_gpa28',
    'min_onet',
    'min_onet01',
    'min_onet02',
    'min_onet03',
    'min_onet04',
    'min_onet05',
    'min_gat',
    'min_gat1',
    'min_gat2',
    'min_pat1and2',
    'min_pat1',
    'min_pat2',
    'min_pat3',
    'min_pat4',
    'min_pat5',
    'min_pat6',
    'min_pat7_1',
    'min_pat7_2',
    'min_pat7_3',
    'min_pat7_4',
    'min_pat7_5',
    'min_pat7_6',
    'min_pat7_7',
    'min_9sub_09',
    'min_9sub_19',
    'min_9sub_29',
    'min_9sub_39',
    'min_9sub_49',
    'min_9sub_59',
    'min_9sub_69',
    'min_9sub_89',
    'min_9sub_99',
    'min_vnet_51',
    'min_vnet_511',
    'min_vnet_512',
    'min_vnet_513',
    'min_vnet_514',
    'min_bnet_393',
    'min_bnet_394',
    'min_inet_31',
    'min_inet_33',
    'min_inet_35',
    'min_inet_38',
    'min_nnet_421',
    'min_nnet_422',
    'min_nnet_423',
    'min_nnet_424',
    'min_nnet_425',
    'min_toefl_ibt',
    'min_toefl_pbt',
    'min_toefl_cbt',
    'min_toefl_ipt',
    'min_ielts',
    'min_toeic',
    'min_cutep',
    'min_tuget',
    'min_kept',
    'min_psutep',
    'min_kuept',
    'min_cmuetegs',
    'min_sat',
    'min_cefr  ',
    'min_ged_score',
    'min_gpa22_23',
    'description',
    'condition',
    'interview_location',
    'interview_date',
    'interview_time',
    'link',
]

SCORE_TYPE_TAGS = [
    #{ "score_type": "GPAX_5_SEMESTER", "description": "ผลการเรียนเฉลี่ยสะสม (GPAX) 5 ภาคเรียน", "unit": "" },
    { "score_type": "GPAX", "description": "ผลการเรียนเฉลี่ยสะสม (GPAX)", "unit": "" },
    { "score_type": "STUDY_AT_12", "description": "เป็นผู้ที่กำลังศึกษาอยู่ชั้นมัธยมศึกษาปีที่ 6 หรือเทียบเท่า", "unit": "" },
    { "score_type": "GRAD_OR_STUDY_AT_12", "description": "กำลังศึกษาหรือสำเร็จศึกษาชั้นมัธยมศึกษาปีที่ 6 หรือเทียบเท่า", "unit": "" },
    { "score_type": "UNIT_MATH", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้คณิตศาสตร์", "unit": "" },
    { "score_type": "UNIT_FOREIGN", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้ภาษาต่างประเทศ", "unit": "" },
    { "score_type": "UNIT_SCI", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้วิทยาศาสตร์", "unit": "" },
    { "score_type": "ONET", "description": "O-NET (5 กลุ่มสาระวิชา)", "unit": "คะแนน" },
    { "score_type": "ONET_THA", "description": "O-NET (01) ภาษาไทย", "unit": "คะแนน" },
    { "score_type": "ONET_SOC", "description": "O-NET (02) สังคมศึกษา", "unit": "คะแนน" },
    { "score_type": "ONET_ENG", "description": "O-NET (03) ภาษาอังกฤษ", "unit": "คะแนน" },
    { "score_type": "ONET_MAT", "description": "O-NET (04) คณิตศาสตร์", "unit": "คะแนน" },
    { "score_type": "ONET_SCI", "description": "O-NET (05) วิทยาศาสตร์", "unit": "คะแนน" },
    { "score_type": "GAT", "description": "GAT", "unit": "คะแนน" },
    { "score_type": "GAT_1", "description": "GAT ส่วน 1", "unit": "คะแนน" },
    { "score_type": "GAT_2", "description": "GAT ส่วน 2", "unit": "คะแนน" },
    { "score_type": "PAT_1", "description": "PAT 1", "unit": "คะแนน" },
    { "score_type": "PAT_2", "description": "PAT 2", "unit": "คะแนน" },
    { "score_type": "PAT_3", "description": "PAT 3", "unit": "คะแนน" },
    { "score_type": "PAT_4", "description": "PAT 4", "unit": "คะแนน" },
    { "score_type": "PAT_5", "description": "PAT 5", "unit": "คะแนน" },
    { "score_type": "PAT_6", "description": "PAT 6", "unit": "คะแนน" },
    #{ "score_type": "PAT_7_1", "description": "PAT 7", "unit": "คะแนน" },
    { "score_type": "PAT_7_1", "description": "PAT 7.1", "unit": "คะแนน" },
    { "score_type": "PAT_7_2", "description": "PAT 7.2", "unit": "คะแนน" },
    { "score_type": "PAT_7_3", "description": "PAT 7.3", "unit": "คะแนน" },
    { "score_type": "PAT_7_4", "description": "PAT 7.4", "unit": "คะแนน" },
    { "score_type": "PAT_7_5", "description": "PAT 7.5", "unit": "คะแนน" },
    { "score_type": "PAT_7_6", "description": "PAT 7.6", "unit": "คะแนน" },
    { "score_type": "PAT_7_7", "description": "PAT 7.7", "unit": "คะแนน" },
    { "score_type": "TOEFL_PBT_ITP", "description": "TOEFL PBT/ITP", "unit": "คะแนน" },
    { "score_type": "TOEFL_CBT", "description": "TOEFL CBT", "unit": "คะแนน" },
    { "score_type": "TOEFL_IBT", "description": "TOEFL IBT", "unit": "คะแนน" },
    { "score_type": "IELTS", "description": "IELTS", "unit": "คะแนน" },
    { "score_type": "OOPT", "description": "OOPT", "unit": "คะแนน" },
    { "score_type": "KU_EPT", "description": "KU-EPT", "unit": "คะแนน" },
    { "score_type": "9SUB", "description": "วิชาสามัญ 9 วิชา", "unit": "คะแนน" },
    { "score_type": "UDAT_09", "description": "วิชาสามัญ ภาษาไทย (09)", "unit": "คะแนน" },
    { "score_type": "UDAT_19", "description": "วิชาสามัญ สังคมศึกษา (19)", "unit": "คะแนน" },
    { "score_type": "UDAT_29", "description": "วิชาสามัญ ภาษาอังกฤษ (29)", "unit": "คะแนน" },
    { "score_type": "UDAT_39", "description": "วิชาสามัญ คณิตศาสตร์ 1 (39)", "unit": "คะแนน" },
    { "score_type": "UDAT_49", "description": "วิชาสามัญ ฟิสิกส์ (49)", "unit": "คะแนน" },
    { "score_type": "UDAT_59", "description": "วิชาสามัญ เคมี (59)", "unit": "คะแนน" },
    { "score_type": "UDAT_69", "description": "วิชาสามัญ ชีววิทยา (69)", "unit": "คะแนน" },
    { "score_type": "UDAT_89", "description": "วิชาสามัญ คณิตศาสตร์ 2 (89)", "unit": "คะแนน" },
    { "score_type": "UDAT_99", "description": "วิชาสามัญ วิทยาศาสตร์ทั่วไป (99)", "unit": "คะแนน" },

    # HACK
    { "score_type": "GPAX", "description": "ผลการเรียนเฉลี่ยสะสม (GPAX) 6 ภาคเรียน", "unit": "" },
    { "score_type": "GPAX", "description": "ผลการเรียนเฉลี่ยสะสม (GPAX) ไม่ต่ำกว่า", "unit": "" },
    { "score_type": "ONET_ENG", "description": "O-NET 03 ภาษาอังกฤษ", "unit": "คะแนน" },
    { "score_type": "ONET_ENG", "description": "O-NET (03)", "unit": "คะแนน" },
    { "score_type": "ONET_ENG", "description": "O-NET (03) ภาษาอังกฤษ ไม่ต่ำกว่า", "unit": "คะแนน" },
    { "score_type": "ONET_MAT", "description": "O-NET (04) วิชาคณิตศาสตร์", "unit": "คะแนน" },
    { "score_type": "GAT", "description": "GAT85", "unit": "คะแนน" },
    { "score_type": "GAT", "description": "GAT ไม่ตำ่กว่า", "unit": "คะแนน" },
    { "score_type": "GAT", "description": "GAT (85): วิชาความถนัดทั่วไป", "unit": "คะแนน" },
    { "score_type": "PAT_1", "description": "PAT I ความถนัดทางคณิตศาสตร์", "unit": "คะแนน" },
    { "score_type": "PAT_1", "description": "PAT1 (71): วิชาความถนัดทางคณิตศาสตร์", "unit": "คะแนน" },
    { "score_type": "PAT_2", "description": "PAT2 (72): วิชาความถนัดทางวิทยาศาสตร์", "unit": "คะแนน" },
    { "score_type": "PAT_5", "description": "PAT 5 ไม่ต่ำกว่า", "unit": "คะแนน" },
    { "score_type": "UNIT_MATH", "description": "กลุ่มสาระการเรียนรู้คณิตศาสตร์", "unit": "" },
    { "score_type": "UNIT_MATH", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้คณิตศาสตร์ (แผนการเรียนวิทยาศาสตร์-คณิตศาสตร์)", "unit": "" },
    { "score_type": "UNIT_MATH", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้คณิตศาสตร์ (แผนการเรียนศิลป์คำนวณ)", "unit": "" },
    { "score_type": "UNIT_MATH", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้คณิตศาสตร์ ไม่น้อยกว่า", "unit": "" },
    { "score_type": "UNIT_MATH", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้คณิตศาสตร์ ต้องเรียนรายวิชาพื้นฐานและรายวิชาเพิ่มเติม รวมกัน", "unit": "" },
    { "score_type": "UNIT_MATH", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้คณิตศาสตร์ (แผนการเรียนศิลป์คำนวณ) ไม่ต่ำกว่า 12.00", "unit": "" },
    { "score_type": "UNIT_MATH", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้คณิตศาสตร์ ต้องเรียนรายวิชาพื้นฐานและรายวิชาเพิ่มเติมรวมกัน", "unit": "" },
    { "score_type": "UNIT_MATH", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้คณิตศาสตร์ ต้องเรียนรายวิชาพิ้นฐานและรายวิชาเพิ่มเติม รวมกัน", "unit": "" },
    { "score_type": "UNIT_MATH", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้คณิตศาสตร์ ไม่น้อยกว่า", "unit": "" },
    { "score_type": "UNIT_MATH", "description": "หน่วยกิจกลุ่มสาระคณิตศาสตร์", "unit": "" },
    { "score_type": "UNIT_MATH", "description": "หน่วยกิตกลุ่มสาระคณิตศาสตร์", "unit": "" },

    { "score_type": "UNIT_FOREIGN", "description": "กลุ่มสาระการเรียนรู้ภาษาต่างประเทศ", "unit": "" },
    { "score_type": "UNIT_FOREIGN", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้ภาษาต่างประเทศ (แผนการเรียนวิทยาศาสตร์-คณิตศาสตร์)", "unit": "" },
    { "score_type": "UNIT_FOREIGN", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้ภาษาต่างประเทศ (ภาษาอังกฤษ)", "unit": "" },
    { "score_type": "UNIT_FOREIGN", "description": "หน่วยกิจกลุ่มสาระภาษาต่างประเทศ", "unit": "" },
    { "score_type": "UNIT_FOREIGN", "description": "หน่วยกิตกลุ่มสาระภาษาต่างประเทศ", "unit": "" },

    { "score_type": "UNIT_SCI", "description": "กลุ่มสาระการเรียนรู้วิทยาศาสตร์", "unit": "" },
    { "score_type": "UNIT_SCI", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้วิทยาศาสตร์ (แผนการเรียนวิทยาศาสตร์-คณิตศาสตร์)", "unit": "" },
    { "score_type": "UNIT_SCI", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้วิทยาศาสตร์ (แผนการเรียนศิลป์คำนวณ)", "unit": "" },
    { "score_type": "UNIT_SCI", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้วิทยาศาสตร์ ไม่น้อยกว่า", "unit": "" },
    { "score_type": "UNIT_SCI", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้วิทยาศาสตร์ ต้องเรียนรายวิชาพื้นฐานและรายวิชาเพิ่มเติม รวมกัน", "unit": "" },
    { "score_type": "UNIT_SCI", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้วิทยาศาสตร์ ต้องเรียนรายวิชาพื้นฐานและรายวิชาเพิ่มเติมรวมกัน", "unit": "" },
    { "score_type": "UNIT_SCI", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้วิทยาศาสตร์ ต้องเรียนวิชาพื้นฐานและรายวิชาเพิ่มเติม รวมกัน", "unit": "" },
    { "score_type": "UNIT_SCI", "description": "เรียนรายวิชาในกลุ่มสาระการเรียนรู้วิทยาศาสตร์ ไม่น้อยกว่า", "unit": "" },
    { "score_type": "UNIT_SCI", "description": "หน่วยกิตกลุ่มสาระวิทยาศาสตร์", "unit": "" },
    
    { "score_type": "GAT_2", "description": "GAT (ตอน 2 ภาษาอังกฤษ)", "unit": "คะแนน" },
    { "score_type": "GAT_2", "description": "GAT ตอน 2", "unit": "คะแนน" },
    { "score_type": "GAT_2", "description": "GAT ตอน2", "unit": "คะแนน" },
    { "score_type": "GAT_2", "description": "GAT General (English)", "unit": "คะแนน" },

    { "score_type": "GPAX", "description": "ผลการเรียนเฉลี่ยสะสม (GPAX) 5 ภาคเรียน", "unit": "" },
    { "score_type": "UDAT_09", "description": "วิชา 09", "unit": "คะแนน" },
    { "score_type": "UDAT_19", "description": "วิชา 19", "unit": "คะแนน" },
    { "score_type": "UDAT_29", "description": "วิชา 29", "unit": "คะแนน" },
    { "score_type": "UDAT_29", "description": "29", "unit": "คะแนน" },
    { "score_type": "UDAT_39", "description": "วิชา 39", "unit": "คะแนน" },
    { "score_type": "UDAT_49", "description": "วิชา 49", "unit": "คะแนน" },
    { "score_type": "UDAT_59", "description": "วิชา 59", "unit": "คะแนน" },
    { "score_type": "UDAT_69", "description": "วิชา 69", "unit": "คะแนน" },
    { "score_type": "UDAT_89", "description": "วิชา 89", "unit": "คะแนน" },
    { "score_type": "UDAT_99", "description": "วิชา 99", "unit": "คะแนน" },


    # HACK ad1
    { "score_type": 'CW701', 'description': '7 (รูปแบบที่ 1): **** ยังไม่ได้เลือก PAT **** กลุ่ม 7 ครุศาสตร์ ศึกษาศาสตร์ พลศึกษา สุขศึกษา (รูปแบบที่ 1)' },
    { "score_type": 'CW701', 'description': '7 (รูปแบบที่ 1) กลุ่ม 7 ครุศาสตร์ ศึกษาศาสตร์ พลศึกษา สุขศึกษา (รูปแบบที่ 1)' },
    { "score_type": 'CW140', 'description': '1.4: กลุ่ม 1 วิทยาศาสตร์สุขภาพ - สัตวแพทย์ศาสตร์' },
    { "score_type": 'CW110', 'description': '1.1: กลุ่ม 1 วิทยาศาสตร์สุขภาพ - สัตวแพทย์ศาสตร์ สหเวชศาสตร์ สาธารณสุขศาสตร์ เทคนิคการแพทย์ พยาบาลศาสตร์ วิทยาศาสตร์การกีฬา' },

    { "score_type": 'MIN_GPA21', 'description': 'ผลการเรียนเฉลี่ยรวมของกลุ่มสาระการเรียนรู้ภาษาไทย'},
    { "score_type": 'MIN_GPA22', 'description': 'คะแนนเฉลี่ยกลุ่มสาระคณิตศาสตร์'},
    { "score_type": 'MIN_GPA22', 'description': 'มีคะแนนเฉลี่ยกลุ่มสาระคณิตศาสตร์'},
    { "score_type": 'MIN_GPA22', 'description': 'ผลการเรียนกลุ่มสาระการเรียนรู้คณิตศาสตร์'},
    { "score_type": 'MIN_GPA23', 'description': 'คะแนนเฉลี่ยกลุ่มสาระวิทยาศาสตร์'},
    { "score_type": 'MIN_GPA23', 'description': 'มีคะแนนเฉลี่ยกลุ่มสาระวิทยาศาสตร์'},
    { "score_type": 'MIN_GPA23', 'description': 'ผลการเรียนกลุ่มสาระการเรียนรู้วิทยาศาสตร์'},
    { "score_type": 'MIN_GPA28', 'description': 'มีคะแนนเฉลี่ยกลุ่มสาระภาษาต่างประเทศ'},
    { "score_type": 'MIN_GPA28', 'description': 'ผลการเรียนเฉลี่ยรวมของกลุ่มสาระการเรียนรู้ภาษาต่างประเทศ'},
]

for t,d in COMPONENT_WEIGHT_TYPE_CHOICES:
    SCORE_TYPE_TAGS.append({"score_type": t, "description": d})

COMPONENT_WEIGHT_OPTIONS = [
    ('CW110','1.1',0),
    ('CW120','1.2',0),
    ('CW130','1.3',0),
    ('CW140','1.4',0),
    ('CW210','2.1',0),
    ('CW220','2.2',0),
    ('CW300','3',0),
    ('CW400','4',0),
    ('CW500','5',0),
    ('CW610','6.1',0),
    ('CW621','6.2.1',0),
    ('CW62271','6.2.2','PAT7.1'),
    ('CW62272','6.2.2','PAT7.2'),
    ('CW62273','6.2.2','PAT7.3'),
    ('CW62274','6.2.2','PAT7.4'),
    ('CW62275','6.2.2','PAT7.5'),
    ('CW62276','6.2.2','PAT7.6'),
    ('CW62277','6.2.2','PAT7.7'),
    ('CW701','7.1',0),
    ('CW7021','7.2','PAT1'),
    ('CW7022','7.2','PAT2'),
    ('CW7023','7.2','PAT3'),
    ('CW7024','7.2','PAT4'),
    ('CW7026','7.2','PAT6'),
    ('CW70271','7.2','PAT7.1'),
    ('CW70272','7.2','PAT7.2'),
    ('CW70273','7.2','PAT7.3'),
    ('CW70274','7.2','PAT7.4'),
    ('CW70275','7.2','PAT7.5'),
    ('CW70276','7.2','PAT7.6'),
    ('CW70277','7.2','PAT7.7'),
    ('CW8004','8','PAT4'),
    ('CW8006','8','PAT6'),
    ('CW910','9.1',0),
    ('CW921','9.2.1',0),
    ('CW92271','9.2.2','PAT7.1'),
    ('CW92272','9.2.2','PAT7.2'),
    ('CW92273','9.2.2','PAT7.3'),
    ('CW92274','9.2.2','PAT7.4'),
    ('CW92275','9.2.2','PAT7.5'),
    ('CW92276','9.2.2','PAT7.6'),
    ('CW92277','9.2.2','PAT7.7'),
]


COMPONENT_WEIGHT_MAP = { c[0]:(c[1],c[2]) for c in COMPONENT_WEIGHT_OPTIONS }

SCORE_TYPE_REVERSE_MAP = dict([
    (t['description'].strip(), t['score_type'].strip())
    for t in SCORE_TYPE_TAGS
])

SCORE_TYPE_FIELD_MAP = {
    "GPAX_5_SEMESTER": 'ERROR',
    "GPAX": "min_gpax",
    "UNIT_MATH": 'min_credit_gpa22',
    "UNIT_FOREIGN": 'min_credit_gpa28',
    "UNIT_SCI": 'min_credit_gpa23',
    "ONET": 'min_onet',
    "ONET_THA": 'min_onet01',
    "ONET_SOC": 'min_onet02',
    "ONET_ENG": 'min_onet03',
    "ONET_MAT": 'min_onet04',
    "ONET_SCI": 'min_onet05',
    "GAT": 'min_gat',
    "GAT_1": 'min_gat1',
    "GAT_2": 'min_gat2',
    "PAT_1": 'min_pat1',
    "PAT_2": 'min_pat2',
    "PAT_3": 'min_pat3',
    "PAT_4": 'min_pat4',
    "PAT_5": 'min_pat5',
    "PAT_6": 'min_pat6',
    "PAT_7_1": 'min_pat7_1',
    "PAT_7_2": 'min_pat7_2',
    "PAT_7_3": 'min_pat7_3',
    "PAT_7_4": 'min_pat7_4',
    "PAT_7_5": 'min_pat7_5',
    "PAT_7_6": 'min_pat7_6',
    "PAT_7_7": 'min_pat7_7',
    "UDAT_09": 'min_9sub_09',
    "UDAT_19": 'min_9sub_19',
    "UDAT_29": 'min_9sub_29',
    "UDAT_39": 'min_9sub_39',
    "UDAT_49": 'min_9sub_49',
    "UDAT_59": 'min_9sub_59', 
    "UDAT_69": 'min_9sub_69',
    "UDAT_89": 'min_9sub_89',
    "UDAT_99": 'min_9sub_99',

    "MIN_GPA21": 'min_gpa21',
    "MIN_GPA22": 'min_gpa22',
    "MIN_GPA23": 'min_gpa23',
    "MIN_GPA28": 'min_gpa28',
}

def reverse_score_type(score_criteria):
    if score_criteria.score_type != 'OTHER':
        return score_criteria.score_type
    elif score_criteria.description.strip() in SCORE_TYPE_REVERSE_MAP:
        return SCORE_TYPE_REVERSE_MAP[score_criteria.description.strip()]
    else:
        return 'OTHER'

all_missing_descriptions = []
    
def min_score_vector_from_criterias(score_criterias, curriculum_major):
    value_vectors = {}
    for f in FIELDS:
        if f.startswith('min') or f.startswith('max'):
            value_vectors[f] = 0

    if score_criterias == []:
        return value_vectors
            
    is_error = False
    for c in score_criterias:
        score_type = c.score_type
        if score_type == 'OTHER':
            score_type = reverse_score_type(c)
        if c.value != None and c.value > 0:
            if score_type not in SCORE_TYPE_FIELD_MAP:
                print(f'Error missing {score_type} {c} "{c.description.strip()}"')
                all_missing_descriptions.append(c.description)
                is_error = True
            elif SCORE_TYPE_FIELD_MAP[score_type] == 'ERROR':
                #print('Found:', score_type, c)
                print('Error gpax5', c)
                is_error = True
            else:
                value_vectors[SCORE_TYPE_FIELD_MAP[score_type]] = float(c.value)
        else:
            if score_type == 'OTHER':
                is_error = True
                print(f'OTHER - None: Error missing {score_type} {c} "{c.description.strip()}" [{c.value}]')

    if is_error:
        print('=============', curriculum_major.faculty, '==========', curriculum_major.cupt_code)
                
    return value_vectors

def min_score_vectors(admission_criteria, curriculum_major):
    if not admission_criteria:
        return [min_score_vector_from_criterias([], curriculum_major)]

    or_count = 0
    or_criterias = []
    
    is_error = False
    score_criterias = []
    for c in admission_criteria.get_all_required_score_criteria():
        if c.has_children():
            if c.relation != 'AND':
                if c.relation == 'OR':
                    or_count += 1
                    for child in c.childs.all():
                        or_criterias.append(child)
                if (or_count > 1) or (c.relation != 'OR'):
                    print('Error type (or too many OR):', c.relation)
                    for child in c.childs.all():
                        print(f"    - {child}")
                    is_error = True
            else:
                for child in c.childs.all():
                    score_criterias.append(child)
        else:
            score_criterias.append(c)        

    if or_count == 0:
        value_vectors = min_score_vector_from_criterias(score_criterias, curriculum_major)
    
        if is_error:
            print('=============', curriculum_major.faculty, '==========', curriculum_major.cupt_code)
                
        return [value_vectors]
    elif or_count == 1:
        print('OR found:', or_criterias)
        output = []
        for or_criteria in or_criterias:
            this_score_criterias = [c for c in score_criterias] + [or_criteria]
            
            value_vectors = min_score_vector_from_criterias(this_score_criterias, curriculum_major)

            output.append(value_vectors)
            
        if is_error:
            print('=============', curriculum_major.faculty, '==========', curriculum_major.cupt_code)

        return output

    else:
        value_vectors = min_score_vector_from_criterias(score_criterias, curriculum_major)
    
        if is_error:
            print('TOO MANY ORs =============', curriculum_major.faculty, '==========', curriculum_major.cupt_code)
                
        return [value_vectors]


def update_component_weight(row, admission_criteria, curriculum_major):
    score_criterias = []
    is_error = False
    is_assigned = False
    
    for c in admission_criteria.get_all_scoring_score_criteria():
        if c.has_children():
            print('Error type:', c.relation)
            for child in c.childs.all():
                print(f"    - {child}")
                is_error = True
        else:
            score_criterias.append(c)        

    if len(score_criterias) != 1:
        print('Too many', len(score_criterias))
        is_error = True
        
    for c in score_criterias:
        score_type = c.score_type
        if score_type == 'OTHER':
            score_type = reverse_score_type(c)

        if score_type in COMPONENT_WEIGHT_MAP:
            cw, cpat = COMPONENT_WEIGHT_MAP[score_type]
            row['component_weight'] = cw
            row['component_pat'] = cpat
            is_assigned = True
        else:
            print('Unknown scoring', c)
            is_error = True

    if not is_assigned:
        print('ERROR not assigned')
        
    if is_error or (not is_assigned):
        print("----------------", curriculum_major.cupt_code)

def main():
    project_ids = sys.argv[1:]

    for project_id in project_ids:
        admission_project = AdmissionProject.objects.get(pk=project_id)

        faculties = Faculty.objects.all()
    
        admission_criterias = (AdmissionCriteria
                               .objects
                               .filter(admission_project_id=project_id,
                                       is_deleted=False)
                               .order_by('faculty_id'))

        for admission_criteria in admission_criterias:

            #if admission_criteria.id not in [7425]:
            #    continue
            
            curriculum_major_criterias = admission_criteria.curriculummajoradmissioncriteria_set.all()

            if len(curriculum_major_criterias) == 0:
                continue
            
            curriculum_major = curriculum_major_criterias[0].curriculum_major

            min_scores_vecs = min_score_vectors(admission_criteria, curriculum_major)
            if len(min_scores_vecs) > 1:
                print('ERROR two rows', curriculum_major)
            min_scores = min_scores_vecs[0]

            non_zero_min_scores = { k:min_scores[k] for k in min_scores if min_scores[k] > 0 }

            if admission_criteria.additional_condition != '':
                non_zero_min_scores['additional_condition'] = admission_criteria.additional_condition
                print(" > ", curriculum_major, "---->", admission_criteria.additional_condition)
            
            min_scores_json = json.dumps(non_zero_min_scores)
            #print(curriculum_major, admission_criteria.id, min_scores_json)

            admission_criteria.min_scores_json = min_scores_json
            admission_criteria.save()


if __name__ == '__main__':
    main()
