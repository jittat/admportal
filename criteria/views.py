import json

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponseForbidden

from majors.models import Faculty, Campus, AdmissionProject, AdmissionRound
from .models import CurriculumMajor, MajorCuptCode, AdmissionCriteria

HIDE_CRITERIA = False

DEFAULT_CAMPUS_ID = 1

def build_choices(campuses, faculties, current_selection=None):
    choices = []
    for c in campuses:
        is_selected = False
        if current_selection and type(current_selection) == Campus:
            if current_selection.id == c.id:
                is_selected = True
        choices.append({ 'type': 'campus',
                         'obj': c,
                         'id': c.id,
                         'label': c.title,
                         'short_label': c.short_title,
                         'is_selected': is_selected })
        for f in [f for f in faculties if f.campus_id == c.id]:
            is_selected = False
            if current_selection and type(current_selection) == Faculty:
                if current_selection.id == f.id:
                    is_selected = True
            choices.append({ 'type': 'faculty',
                             'obj': f,
                             'id': f.id,
                             'label': f.title,
                             'short_label': f.title,
                             'is_selected': is_selected })

    return choices

def update_campus_keys():
    for c in MajorCuptCode.objects.filter(campus=None).all():
        c.campus = c.faculty.campus
        c.save()
        
    for c in CurriculumMajor.objects.filter(campus=None).all():
        c.campus = c.faculty.campus
        c.save()

def update_project_list():
    codes = MajorCuptCode.objects.all()
    project_sets = {}
    for curriculum_major in CurriculumMajor.objects.all():
        code_id = curriculum_major.cupt_code_id
        if code_id not in project_sets:
            project_sets[code_id] = set()
        project_sets[code_id].add(curriculum_major.admission_project_id)

    for c in codes:
        if c.id not in project_sets:
            pstr = ''
        else:
            pstr = ','.join([str(i) for i in project_sets[c.id]])
            
        c.admission_project_list = pstr
        c.save()
        print(c)


def index(request, campus_id=None, faculty_id=None):
    if HIDE_CRITERIA:
        return HttpResponseForbidden()
    
    if campus_id==None and faculty_id==None:
        return redirect(reverse('criteria:index-campus',
                                kwargs={'campus_id':DEFAULT_CAMPUS_ID}))

    #update_campus_keys()
    #update_project_list()
    
    all_campuses = Campus.objects.all()
    all_faculties = Faculty.objects.all()
    all_projects = AdmissionProject.objects.filter(is_available=True).order_by('display_rank').all()

    selected_obj = None

    if faculty_id!=None:
        faculty = get_object_or_404(Faculty, pk=faculty_id)
        campus = faculty.campus
        faculties = [faculty]
        selected_obj = faculty
        selected_label = faculty
        major_codes = MajorCuptCode.objects.filter(faculty=faculty).all()
        curriculum_majors = CurriculumMajor.objects.filter(faculty=faculty).all()
    else:
        campus = get_object_or_404(Campus, pk=campus_id)
        faculties = Faculty.objects.filter(campus=campus).all()
        selected_obj = campus
        selected_label = campus.title
        
        major_codes = MajorCuptCode.objects.filter(campus=campus).order_by('faculty').all()
        curriculum_majors = CurriculumMajor.objects.filter(campus=campus).all()

    selected_project_ids = set()
    for m in major_codes:
        selected_project_ids.update(m.get_admission_project_set())

    selected_projects = [p for p in all_projects
                         if p.id in selected_project_ids]
        
    round_numbers = sorted(set([p.default_round_number for p in selected_projects]))

    choices = build_choices(all_campuses, all_faculties, selected_obj)

    return render(request,
                  'criteria/index.html',
                  { 'choices': choices,
                    'selected_obj': selected_obj,
                    'selected_label': selected_label,
                    'selected_projects': selected_projects,
                    'round_numbers': round_numbers,
                    'campus': campus,
                    'major_codes': major_codes })


def sort_admission_criteria_rows(admission_criteria_rows):
    lst = []
    for criteria in admission_criteria_rows:
        first_criteria = criteria['criterias'][0]
        key = '-'.join([mc.curriculum_major.cupt_code.program_code + mc.curriculum_major.cupt_code.major_code for mc in criteria['majors']])
        total_slots = sum([mc.slots for mc in criteria['majors']])
        lst.append((first_criteria.faculty_id, key, -total_slots, first_criteria.id, criteria))

    return [item[4] for item in sorted(lst)]

def combine_criteria_rows(rows):
    major_slots = {}

    for r in rows:
        curriculum_major_admission_criterias = r['majors']
        for mc in curriculum_major_admission_criterias:
            major = mc.curriculum_major
            major_id = mc.curriculum_major.id
            if major_id not in major_slots:
                major_slots[major_id] = []
            major_slots[major_id].append((mc.slots, mc, r['criterias'][0]))

    combined_rows = []
    deleted_major_ids = set()
            
    for major_id in major_slots:
        slots = major_slots[major_id]
        if len(slots) > 1:
            non_zero_mc = [s for s in slots if s[0] > 0]
            if len(non_zero_mc) == 1:
                combined_rows.append({
                    'majors': [non_zero_mc[0][1]],
                    'criterias': [s[2] for s in slots],
                    'major_count': 1,
                    'criteria_count': len(slots),
                })

                for _,mc,_ in slots:
                    deleted_major_ids.add(mc.id)

    output_rows = []

    for r in rows:
        curriculum_major_admission_criterias = r['majors']
        output_majors = []
        for mc in curriculum_major_admission_criterias:
            if mc.id not in deleted_major_ids:
                output_majors.append(mc)

        if len(output_majors) != 0:
            output_rows.append({
                'majors': output_majors,
                'criterias': r['criterias'],
                'major_count': len(output_majors),
                'criteria_count': len(r['criterias']),
            })

    return output_rows + combined_rows
        
def prepare_admission_criteria(admission_criterias, curriculum_majors, combine_majors=False):
    curriculum_majors_with_criterias = []
    for criteria in admission_criterias:
        criteria.cache_score_criteria_children()
        criteria.curriculum_major_admission_criterias = criteria.curriculummajoradmissioncriteria_set.select_related('curriculum_major').all()
        criteria.curriculum_major_admission_criteria_count = len(criteria.curriculum_major_admission_criterias)
        criteria.curriculum_majors = [mj.curriculum_major for mj in criteria.curriculum_major_admission_criterias]
        curriculum_majors_with_criterias += criteria.curriculum_majors

    curriculum_majors_with_criteria_ids = set([m.id for m
                                               in curriculum_majors_with_criterias])

    free_curriculum_majors = [m for m in curriculum_majors
                              if m.id not in curriculum_majors_with_criteria_ids]

    admission_criteria_rows = [{'majors': c.curriculum_major_admission_criterias,
                                'criterias': [c],
                                'major_count': len(c.curriculum_major_admission_criterias),
                                'criteria_count': len([c])} for c in admission_criterias]

    if combine_majors:
        admission_criteria_rows = combine_criteria_rows(admission_criteria_rows)

    return sort_admission_criteria_rows(admission_criteria_rows), free_curriculum_majors

def get_all_curriculum_majors(project, faculty=None):
    if not faculty:
        majors = CurriculumMajor.objects.filter(
            admission_project_id=project.id).select_related('cupt_code')
    else:
        majors = CurriculumMajor.objects.filter(
            admission_project_id=project.id,
            faculty_id=faculty.id).select_related('cupt_code')

    return majors

MIN_SCORE_COLUMNS = [
    'min_credit_gpa22',
    'min_credit_gpa23',
    'min_credit_gpa28',
    'min_gpax',
    'min_onet03',
    'min_gat',
    'min_pat1',
    'min_pat2',
    'min_pat3',
    'min_pat4',
    'min_pat5',
]

EXTRA_NAME_MAP = {
    'min_onet01':'ONET01',
    'min_onet04':'ONET04',
    'min_onet05':'ONET05',
    'min_pat7_1':'PAT7.1',
    'min_pat7_2':'PAT7.2',
    'min_pat7_3':'PAT7.3',
    'min_pat7_4':'PAT7.4',
    'min_pat7_5':'PAT7.5',
    'min_pat7_6':'PAT7.6',
    'min_pat7_7':'PAT7.7',
    'min_9sub_09':'สามัญ09',
    'min_9sub_19':'สามัญ19',
    'min_9sub_29':'สามัญ29',
    'min_9sub_39':'สามัญ39',
    'min_9sub_49':'สามัญ49',
    'min_9sub_59':'สามัญ59',
    'min_9sub_69':'สามัญ69',
    'min_9sub_89':'สามัญ89',
    'min_gat2':'GAT(ส่วน2)',
    'min_gpa21':'คะแนนเฉลี่ยกลุ่มสาระไทย',
    'min_gpa22':'คะแนนเฉลี่ยกลุ่มสาระคณิต',
    'min_gpa23':'คะแนนเฉลี่ยกลุ่มสาระวิทย์',
    'min_gpa28':'คะแนนเฉลี่ยกลุ่มสาระภาษาตปท.',

    'PAT_1': 'PAT1',
    'PAT_2': 'PAT2',
    'PAT_3': 'PAT3',
    'PAT_4': 'PAT4',
    'PAT_5': 'PAT5',
    'PAT_6': 'PAT6',
    'PAT_7_1': 'PAT7.1',
    'PAT_7_2': 'PAT7.2',
    'PAT_7_3': 'PAT7.3',
    'PAT_7_4': 'PAT7.4',
    'PAT_7_5': 'PAT7.5',
    'PAT_7_6': 'PAT7.6',
    'PAT_7_7': 'PAT7.7',

    'UDAT_09': 'สามัญ09',
    'UDAT_19': 'สามัญ19',
    'UDAT_29': 'สามัญ29',
    'UDAT_39': 'สามัญ39',
    'UDAT_49': 'สามัญ49',
    'UDAT_59': 'สามัญ59',
    'UDAT_69': 'สามัญ69',
    'UDAT_89': 'สามัญ89',
    'UDAT_99': 'สามัญ99',

    'ONET_THA': 'ONET01',
    'ONET_SOC': 'ONET02',
    'ONET_ENG': 'ONET03',
    'ONET_MAT': 'ONET04',
    'ONET_SCI': 'ONET05',
    'MAX(UDAT_39,UDAT_89)': 'วิชาสามัญ39 หรือ วิชาสามัญ89',

    'CW110':'กลุ่ม 1 วิทยาศาสตร์สุขภาพ - 1.1 สหเวชศาสตร์ สาธารณสุขศาสตร์ เทคนิคการแพทย์ พยาบาลศาสตร์ วิทยาศาสตร์การกีฬา',
    'CW120':'กลุ่ม 1 วิทยาศาสตร์สุขภาพ - 1.2 ทันตแพทย์ศาสตร์',
    'CW130':'กลุ่ม 1 วิทยาศาสตร์สุขภาพ - 1.3 เภสัชศาสตร์',
    'CW140':'กลุ่ม 1 วิทยาศาสตร์สุขภาพ - 1.4 สัตวแพทย์ศาสตร์',
    'CW210':'กลุ่ม 2 วิทยาศาสตร์กายภาพและชีวภาพ - 2.1 วิทยาศาสตร์ ทรัพยากรธรรมชาติ',
    'CW220':'กลุ่ม 2 วิทยาศาสตร์กายภาพและชีวภาพ - 2.2 เทคโนโลยีสารสนเทศ',
    'CW300': 'กลุ่ม 3 วิศวกรรมศาสตร์',
    'CW400': 'กลุ่ม 4 สถาปัตยกรรมศาสตร์',
    'CW500': 'กลุ่ม 5 เกษตรศาสตร์ - เกษตรศาสตร์ อุตสาหกรรมเกษตร วนศาสตร์ เทคโนโลยีการเกษตร',
    'CW610': 'กลุ่ม 6 - 6.1 บริหารธุรกิจ พาณิชยศาสตร์ การบัญชี เศรษฐศาสตร์',
    'CW621': 'กลุ่ม 6 - 6.2 การท่องเที่ยวและการโรงแรม (รูปแบบที่ 1)',
    'CW62271': 'กลุ่ม 6 - 6.2 การท่องเที่ยวและการโรงแรม (รูปแบบที่ 2 PAT 7.1 ฝรั่งเศษ)',
    'CW62272': 'กลุ่ม 6 - 6.2 การท่องเที่ยวและการโรงแรม (รูปแบบที่ 2 PAT 7.2 เยอรมัน)',
    'CW62273': 'กลุ่ม 6 - 6.2 การท่องเที่ยวและการโรงแรม (รูปแบบที่ 2 PAT 7.3 ญี่ปุ่น)',
    'CW62274': 'กลุ่ม 6 - 6.2 การท่องเที่ยวและการโรงแรม (รูปแบบที่ 2 PAT 7.4 จีน)',
    'CW62275': 'กลุ่ม 6 - 6.2 การท่องเที่ยวและการโรงแรม (รูปแบบที่ 2 PAT 7.5 อาหรับ)',
    'CW62276': 'กลุ่ม 6 - 6.2 การท่องเที่ยวและการโรงแรม (รูปแบบที่ 2 PAT 7.6 บาลี)',
    'CW62277': 'กลุ่ม 6 - 6.2 การท่องเที่ยวและการโรงแรม (รูปแบบที่ 2 PAT 7.7 เกาหลี)',
    'CW701': 'กลุ่ม 7 ครุศาสตร์ ศึกษาศาสตร์ พลศึกษา สุขศึกษา (รูปแบบที่ 1)',
    'CW7021': 'กลุ่ม 7 ครุศาสตร์ ศึกษาศาสตร์ พลศึกษา สุขศึกษา (รูปแบบที่ 2 PAT 1 คณิตศาสตร์)',
    'CW7022': 'กลุ่ม 7 ครุศาสตร์ ศึกษาศาสตร์ พลศึกษา สุขศึกษา (รูปแบบที่ 2 PAT 2 วิทยาศาสตร์)',
    'CW7023': 'กลุ่ม 7 ครุศาสตร์ ศึกษาศาสตร์ พลศึกษา สุขศึกษา (รูปแบบที่ 2 PAT 3 วิศวกรรมศาสตร์)',
    'CW7024': 'กลุ่ม 7 ครุศาสตร์ ศึกษาศาสตร์ พลศึกษา สุขศึกษา (รูปแบบที่ 2 PAT 4 สถาปัตยกรรมศาสตร์)',
    'CW7026': 'กลุ่ม 7 ครุศาสตร์ ศึกษาศาสตร์ พลศึกษา สุขศึกษา (รูปแบบที่ 2 PAT 6 ศิลปกรรมศาสตร์)',
    'CW70271': 'กลุ่ม 7 ครุศาสตร์ ศึกษาศาสตร์ พลศึกษา สุขศึกษา (รูปแบบที่ 2 PAT 7.1 ฝรั่งเศส)',
    'CW70272': 'กลุ่ม 7 ครุศาสตร์ ศึกษาศาสตร์ พลศึกษา สุขศึกษา (รูปแบบที่ 2 PAT 7.2 เยอรมัน)',
    'CW70273': 'กลุ่ม 7 ครุศาสตร์ ศึกษาศาสตร์ พลศึกษา สุขศึกษา (รูปแบบที่ 2 PAT 7.3 ญี่ปุ่น)',
    'CW70274': 'กลุ่ม 7 ครุศาสตร์ ศึกษาศาสตร์ พลศึกษา สุขศึกษา (รูปแบบที่ 2 PAT 7.4 จีน)',
    'CW70275': 'กลุ่ม 7 ครุศาสตร์ ศึกษาศาสตร์ พลศึกษา สุขศึกษา (รูปแบบที่ 2 PAT 7.5 อาหรับ)',
    'CW70276': 'กลุ่ม 7 ครุศาสตร์ ศึกษาศาสตร์ พลศึกษา สุขศึกษา (รูปแบบที่ 2 PAT 7.6 บาลี)',
    'CW70277': 'กลุ่ม 7 ครุศาสตร์ ศึกษาศาสตร์ พลศึกษา สุขศึกษา (รูปแบบที่ 2 PAT 7.7 เกาหลี)',
    'CW8004': 'กลุ่ม 8 ศิลปกรรมศาสตร์ (เลือก PAT 4)',
    'CW8006': 'กลุ่ม 8 ศิลปกรรมศาสตร์ (เลือก PAT 6)',
    'CW910': 'กลุ่ม 9 มนุษย์ศาสตร์และสังคมศาสตร์ - 9.1 พื้นฐานวิทยาศาสตร์',
    'CW921': 'กลุ่ม 9 มนุษย์ศาสตร์และสังคมศาสตร์ - 9.2 พื้นฐานศิลปศาสตร์ (รูปแบบที่ 1)',
    'CW92271': 'กลุ่ม 9 มนุษย์ศาสตร์และสังคมศาสตร์ - 9.2 พื้นฐานศิลปศาสตร์ (รูปแบบที่ 2 PAT 7.1 ฝรั่งเศส)',
    'CW92272': 'กลุ่ม 9 มนุษย์ศาสตร์และสังคมศาสตร์ - 9.2 พื้นฐานศิลปศาสตร์ (รูปแบบที่ 2 PAT 7.2 เยอรมัน)',
    'CW92273': 'กลุ่ม 9 มนุษย์ศาสตร์และสังคมศาสตร์ - 9.2 พื้นฐานศิลปศาสตร์ (รูปแบบที่ 2 PAT 7.3 ญี่ปุ่น)',
    'CW92274': 'กลุ่ม 9 มนุษย์ศาสตร์และสังคมศาสตร์ - 9.2 พื้นฐานศิลปศาสตร์ (รูปแบบที่ 2 PAT 7.4 จีน)',
    'CW92275': 'กลุ่ม 9 มนุษย์ศาสตร์และสังคมศาสตร์ - 9.2 พื้นฐานศิลปศาสตร์ (รูปแบบที่ 2 PAT 7.5 อาหรับ)',
    'CW92276': 'กลุ่ม 9 มนุษย์ศาสตร์และสังคมศาสตร์ - 9.2 พื้นฐานศิลปศาสตร์ (รูปแบบที่ 2 PAT 7.6 บาลี)',
    'CW92277': 'กลุ่ม 9 มนุษย์ศาสตร์และสังคมศาสตร์ - 9.2 พื้นฐานศิลปศาสตร์ (รูปแบบที่ 2 PAT 7.7 เกาหลี)',
}
        


def extract_min_scores_json(min_scores_json):
    if min_scores_json:
        min_scores = json.loads(min_scores_json)
    else:
        min_scores = {}

    cols = []
    used = set()
    for k in MIN_SCORE_COLUMNS:
        if k in min_scores:
            cols.append(min_scores[k])
            used.add(k)
        else:
            cols.append('')

    left = []
    for k in min_scores:
        if k not in used:
            if k in EXTRA_NAME_MAP:
                left.append((EXTRA_NAME_MAP[k], min_scores[k]))
            else:
                left.append((k, min_scores[k]))
    return cols, left

def extract_scoring_scores_json(scoring_scores_json):
    if scoring_scores_json == '':
        return []
    raw_scores = json.loads(scoring_scores_json)
    scores = []
    for s in raw_scores:
        if s[0] in EXTRA_NAME_MAP:
            scores.append((EXTRA_NAME_MAP[s[0]], s[1]))
        else:
            scores.append(s)
    return scores

DEFAULT_MESSAGES = {
    2: 'อ่านรายละเอียดได้ที่ <a target="_blank" href="https://admission.kps.ku.ac.th/">เว็บไซต์การรับสมัครวิทยาเขตกำแพงแสน</a>',
    3: 'อ่านรายละเอียดได้ที่ <a target="_blank" href="https://admissions.src.ku.ac.th/">ระบบรับสมัครเข้าศึกษาวิทยาเขตศรีราชา</a>',
    4: 'อ่านรายละเอียดได้ที่ <a target="_blank" href="https://misreg.csc.ku.ac.th/admission/">ระบบรับสมัครวิทยาเขตเฉลิมพระเกียรติจังหวัดสกลนคร</a>',
}

def show_project(request, project_id, faculty_id=None):
    if HIDE_CRITERIA:
        return HttpResponseForbidden()
    
    project = get_object_or_404(AdmissionProject, pk=project_id)
    if not project.major_detail_visible:
        if not request.user.is_authenticated:
            return HttpResponseForbidden()

    faculties = Faculty.objects.all()
    
    admission_criterias = (AdmissionCriteria
                           .objects
                           .filter(admission_project_id=project_id,
                                   is_deleted=False)
                           .order_by('faculty_id'))

    curriculum_majors = get_all_curriculum_majors(project)
    admission_criteria_rows, free_curriculum_majors = prepare_admission_criteria(admission_criterias, curriculum_majors, True)

    free_curriculum_majors = []

    shows_min_criteria_in_table = project_id in []
    shows_scoring_criteria_percent = project_id in []
    hides_percent = (project.default_round_number == 1)
    hides_scoring_prefix_dash = False # project_id == 28

    for r in admission_criteria_rows:
        campus_id = r['criterias'][0].faculty.campus_id
        if campus_id in DEFAULT_MESSAGES:
            r['default_message'] = DEFAULT_MESSAGES[campus_id]
    
    if shows_min_criteria_in_table:
        for r in admission_criteria_rows:
            for c in r['criterias']:
                c.min_score_cols, c.min_score_others = extract_min_scores_json(c.min_scores_json)

    if shows_scoring_criteria_percent:
        for r in admission_criteria_rows:
            for c in r['criterias']:
                c.scoring_score_cols = extract_scoring_scores_json(c.scoring_scores_json)
    
    return render(request,
                  'criteria/report_index.html',
                  {'project': project,
                   'admission_criteria_rows': admission_criteria_rows,
                   'free_curriculum_majors': free_curriculum_majors,
                   'shows_min_criteria_in_table': shows_min_criteria_in_table,
                   'shows_scoring_criteria_percent': shows_scoring_criteria_percent,
                   'hides_scoring_prefix_dash': hides_scoring_prefix_dash,
                   'hides_percent': hides_percent,
                   })
