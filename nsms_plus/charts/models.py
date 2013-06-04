from dateutil.relativedelta import relativedelta
from django.db.models.aggregates import Avg, Count, Sum, Min, Max
from django.db.models.base import Model
import simplejson
from smartmin.models import SmartModel
from django.db import models
from django.conf import settings
import sys


INTERVAL_CHOICES = (
    ('days', 'days'),
    ('weeks', 'weeks'),
    ('months', 'months'),
    ('years', 'years'),
)

STACK_CHOICES = (
    ('none', 'None'),
    ('normal', 'Normal'),
    ('percent', 'Percent'),
)

DATA_POINTS = 11
AGGREGATES = dict(avg=Avg, sum=Sum, count=Count, max=Max, min=Min)

class Report(SmartModel):
    name = models.CharField(max_length=32, help_text='A short name for this report')
    description = models.TextField(help_text='An optional description for the report')
    charts = models.ManyToManyField('Chart', blank=True, null=True)

    def __unicode__(self):
        return self.name

class Chart (SmartModel):

    title = models.CharField(max_length=255, help_text='The title for this chart')
    subtitle = models.CharField(max_length=255, help_text='The subtitle shown below the title', blank=True, null=True)
    show_axis_y = models.BooleanField(default=False, help_text='Hide or show the Y axis lines')
    axis_x = models.CharField(max_length=255, help_text='The label on the bottom of the chart', blank=True, null=True)
    axis_y = models.CharField(max_length=255, help_text='The label on the left of the chart', blank=True, null=True)
    axis_y2 = models.CharField(max_length=255, help_text='The label on the right of the chart', blank=True, null=True)

    model_class = models.CharField(max_length=255, help_text='The model values to plot', null=False)
    interval = models.CharField(max_length=32, default='weeks', choices=INTERVAL_CHOICES, help_text='The period how values are grouped')
    stacked = models.CharField(max_length=32, choices=STACK_CHOICES, blank=True, null=True)

    def __unicode__(self):
        return self.title

    def to_dict(self):
        chart = dict(interval=self.interval, id=self.pk)
        labels = dict(title=self.title, subtitle=self.subtitle, x=self.axis_x,
                      show_axis_y=self.show_axis_y, y=self.axis_y, y2=self.axis_y2)
        chart['labels'] = labels
        chart['dataset'] = self.model_class
        chart['options'] = dict(stacked=self.stacked)

        metrics = []
        for series in self.series.order_by('order'):
            metrics.append(series.to_json())
        chart['metrics'] = metrics

        return chart

    @classmethod
    def get_series_data(cls, model_class, metric, interval, aggregate, filters):
        model_config = Chart.get_model_config(model_class)
        if model_config:

            model = Chart.get_model(model_class)
            import datetime, qsstats

            date_field = 'created_on'
            if 'date_field' in model_config:
                date_field = model_config['date_field']

            qs = model.objects.all()
            if filters:
                for field,value in filters.iteritems():
                    qs = qs.filter(**{ field : value})

            if aggregate:
                aggregate = AGGREGATES[aggregate](metric)

            qss = qsstats.QuerySetStats(qs, date_field, aggregate=aggregate)

            end = datetime.date.today()
            start = end - datetime.timedelta(days=7)

            if interval == "weeks":
                end += datetime.timedelta(days = 5 - end.weekday())
                start = end - relativedelta(weeks=DATA_POINTS)
            elif interval == "months":
                end = datetime.date(end.year, end.month, 1)
                start = end - relativedelta(months=DATA_POINTS)

            elif interval == "years":
                end = datetime.date(end.year, 1, 1)
                # end -= datetime.timedelta(days=1)
                start = end - relativedelta(years=DATA_POINTS)

            time_series = qss.time_series(start, end, interval=interval)
            return time_series

    @classmethod
    def get_aggregate_functions(cls):
        aggregates = []
        for key,value in AGGREGATES.iteritems():
            aggregates.append(dict(fn=key, name=key.capitalize()))
        return aggregates

    @classmethod
    def get_property_choices(cls, model_class):
        model = Chart.get_model(model_class)
        if model:
            props = []
            for model_field in model._meta.fields:
                if model_field.get_internal_type() in ['IntegerField', 'DecimalField']:
                    props.append(model_field)
            return props

        raise Exception("Invalid dataset %s" % model_class)

    @classmethod
    def get_model_config(cls, model_class):
        for cfg in settings.DASHBOARD['models']:
            model = cfg['model']
            if model == model_class:
                return cfg

    @classmethod
    def get_intervals(cls, model_class):
        cfg = Chart.get_model_config(model_class)
        if cfg and 'intervals' in cfg:
            return cfg['intervals']
        return ['seconds', 'minutes', 'hours', 'days', 'weeks', 'months', 'years']

    @classmethod
    def get_filters(cls, model_class):
        cfg = Chart.get_model_config(model_class)
        model = Chart.get_model(model_class)
        filters = dict()
        if cfg and 'filters' in cfg:
            for filter in cfg['filters']:
                label = ' '.join([ part.capitalize() for part in filter.split('_') ])
                filters[filter] = dict(label=label, options=model._meta.get_field_by_name(filter)[0].get_choices())

        return filters

    @classmethod
    def get_model(cls, model_class):
        if Chart.get_model_config(model_class):
            path = model_class.split('.')
            module = sys.modules['.'.join(path[:-1])]

            # TODO: should use getattr
            model = module.__dict__[path[len(path)-1]]
            return model



class ChartSeries(Model):

    chart = models.ForeignKey(Chart, help_text='The chart the series belongs to', related_name="series")
    property = models.CharField(max_length=64, help_text='The property of the model to plot')
    label = models.CharField(max_length=255, help_text='The label for this series to be shown on the chart')
    color = models.CharField(max_length=16, help_text='The CSS color value (e.g. RGBA) for the series')
    type = models.CharField(max_length=16, help_text='The style of the series (bar, line, area, spline, etc)')
    aggregate = models.CharField(max_length=16, help_text='The aggregate function to group values')
    left = models.BooleanField(help_text='Should this series plot against the left or right axis')
    order = models.IntegerField(help_text='The drawing order for the series')

    def to_json(self):
        return dict(
            name=self.property,
            label=self.label,
            color=self.color,
            type=self.type,
            agg=self.aggregate,
            left=self.left,
            order=self.order,
            filters= [ f.to_json() for f in self.filters.all() ]
        )

class SeriesFilter(Model):
    series = models.ForeignKey(ChartSeries, help_text='The series that is being filtered', related_name="filters")
    field_name = models.CharField(max_length=64, help_text='The name of the field to filter')
    field_value = models.CharField(max_length=255, help_text='The value to filter for')

    def to_json(self):
        return dict(
            field=self.field_name,
            value=self.field_value)
