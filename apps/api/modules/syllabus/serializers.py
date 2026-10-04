from rest_framework import serializers

from .models import Chapter, Course, ExamTerm, Level, Scheme, Subject, SyllabusGroup, SyllabusReport, Topic


class LevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Level
        fields = ["id", "code", "name", "sort_order"]


class CourseSerializer(serializers.ModelSerializer):
    levels = LevelSerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = ["id", "code", "name", "institute_name", "institute_url", "description", "levels"]


class ExamTermSerializer(serializers.ModelSerializer):
    course = serializers.CharField(source="course.code", read_only=True)

    class Meta:
        model = ExamTerm
        fields = ["id", "course", "code", "name", "exam_start", "exam_end"]


class SchemeSerializer(serializers.ModelSerializer):
    from_term = serializers.CharField(source="from_term.code", read_only=True, default=None)
    to_term = serializers.CharField(source="to_term.code", read_only=True, default=None)

    class Meta:
        model = Scheme
        fields = ["id", "code", "name", "status", "from_term", "to_term", "source_url", "published_at"]


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyllabusGroup
        fields = ["id", "key", "name", "sort_order"]


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ["id", "key", "name", "kind", "sort_order"]


class ChapterSerializer(serializers.ModelSerializer):
    marks_weight = serializers.FloatField(read_only=True)

    class Meta:
        model = Chapter
        fields = [
            "id",
            "key",
            "name",
            "marks_min",
            "marks_max",
            "marks_weight",
            "weight_source",
            "target_practice_sets",
            "target_revisions",
            "target_mocks",
            "est_study_minutes",
            "sort_order",
        ]


class SubjectSerializer(serializers.ModelSerializer):
    group_key = serializers.CharField(source="group.key", read_only=True, default=None)
    chapter_count = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = [
            "id",
            "key",
            "paper_number",
            "name",
            "total_marks",
            "exam_duration_minutes",
            "kind",
            "is_optional",
            "sort_order",
            "group_key",
            "chapter_count",
        ]

    def get_chapter_count(self, obj: Subject) -> int:
        # `list_subjects` prefetches active chapters; fall back to a query elsewhere.
        chapters = getattr(obj, "_prefetched_objects_cache", {}).get("chapters")
        return len(chapters) if chapters is not None else obj.chapters.filter(is_active=True).count()


class SubjectDetailSerializer(SubjectSerializer):
    chapters = serializers.SerializerMethodField()
    course = serializers.CharField(source="scheme.level.course.code", read_only=True)
    level = serializers.CharField(source="scheme.level.code", read_only=True)
    scheme = SchemeSerializer(read_only=True)

    class Meta(SubjectSerializer.Meta):
        fields = [*SubjectSerializer.Meta.fields, "course", "level", "scheme", "chapters"]

    def get_chapters(self, obj: Subject):
        chapters = sorted((c for c in obj.chapters.all() if c.is_active), key=lambda c: (c.sort_order, c.key))
        return ChapterSerializer(chapters, many=True).data


class ChapterDetailSerializer(ChapterSerializer):
    topics = serializers.SerializerMethodField()
    subject = SubjectSerializer(read_only=True)
    course = serializers.CharField(source="subject.scheme.level.course.code", read_only=True)
    level = serializers.CharField(source="subject.scheme.level.code", read_only=True)

    class Meta(ChapterSerializer.Meta):
        fields = [*ChapterSerializer.Meta.fields, "course", "level", "subject", "topics"]

    def get_topics(self, obj: Chapter):
        topics = sorted((t for t in obj.topics.all() if t.is_active), key=lambda t: (t.sort_order, t.key))
        return TopicSerializer(topics, many=True).data


class ReportCreateSerializer(serializers.Serializer):
    node_type = serializers.ChoiceField(choices=SyllabusReport.NodeType.choices)
    node_id = serializers.UUIDField()
    message = serializers.CharField(min_length=5, max_length=1000, trim_whitespace=True)
