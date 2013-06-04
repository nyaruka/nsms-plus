import datetime
from dateutil.relativedelta import relativedelta

from django.forms.forms import Form
from django.db.models import Avg
from django.shortcuts import render_to_response
from django.template import RequestContext
from smartmin.views import *
from django.contrib.auth.decorators import login_required
from rapidsms_httprouter.models import Message
from rapidsms.models import Backend
from django.conf import settings
from .models import Chart, Report

import simplejson as json
from isoweek import Week

class ReportCRUDL(SmartCRUDL):
    model = Report

class ChartForm(Form):
    dataset = forms.ChoiceField(choices=[ (item['model'], item['name']) for item in settings.DASHBOARD['models']])

class ChartCRUDL(SmartCRUDL):
    model = Chart
    actions = ('create', 'read', 'update', 'list', 'dataset', 'editor', 'series', 'detail')
    permissions = True

    class List(SmartListView):
        fields = ('title','created_by', 'modified_on')

        def lookup_field_link(self, context, field, obj):
            return "%s?chart=%s" % (reverse("charts.chart_editor"), obj.id)

    class Dataset(SmartFormView):
        title = "Select Dataset"
        form_class = ChartForm
        def get_success_url(self):
            return "%s?dataset=%s" % (reverse('charts.chart_editor'), self.form.cleaned_data['dataset'])

    class Editor(SmartView, TemplateView):
        def pre_process(self, request, *args, **kwargs):
            if 'chart' not in self.request.REQUEST and 'dataset' not in self.request.REQUEST:
                if len(settings.DASHBOARD['models']) == 1:
                    return HttpResponseRedirect("%s?dataset=%s" % (reverse('charts.chart_editor'), settings.DASHBOARD['models'][0]['model']))
                return HttpResponseRedirect(reverse('charts.chart_dataset'))

        def get_context_data(self, **kwargs):
            context = super(ChartCRUDL.Editor, self).get_context_data(**kwargs)

            if 'chart' in self.request.REQUEST:
                chart = Chart.objects.get(pk=self.request.REQUEST['chart'])
                context['chart'] = simplejson.dumps(chart.to_dict())
                model = chart.model_class
            else:
                model = self.request.REQUEST['dataset']

            props = Chart.get_property_choices(model)
            metrics = []
            for prop in props:

                parts = prop.name.split('_')
                for i in range(len(parts)):
                    parts[i] = parts[i].capitalize()

                label = ' '.join(parts)
                metrics.append(dict(name=prop.name, label=label))

            intervals = Chart.get_intervals(model)
            filters = Chart.get_filters(model)

            context['metrics'] = simplejson.dumps(metrics)
            context['aggregates'] = simplejson.dumps(Chart.get_aggregate_functions())
            context['filters_json'] = simplejson.dumps(filters)
            context['dataset'] = model
            context['intervals'] = intervals
            context['filters'] = filters
            context['interval'] = "months"
            return context

        def post(self, request, *args, **kwargs):

            chart_spec = simplejson.loads(request.REQUEST['chart_spec'])
            chart = Chart()

            if 'chart' in request.REQUEST:
                chart = Chart.objects.get(pk=request.REQUEST['chart'])
            else:
                chart.created_by = request.user
                
            labels = chart_spec['labels']
            chart.modified_by = request.user
            chart.model_class=chart_spec['dataset']
            chart.title=labels['title']
            chart.subtitle=labels['subtitle']
            chart.axis_x=labels['x']
            chart.show_axis_y=labels['show_axis_y']
            chart.axis_y=labels['y']
            chart.axis_y2=labels['y2']
            chart.interval = chart_spec['interval']

            if chart_spec['options']['stacked'] == "none":
                chart.stacked = None
            else:
                chart.stacked = chart_spec['options']['stacked']
                
            chart.save()

            # now let's have a look at the series data
            chart.series.all().delete()

            order = 0
            for metric in chart_spec['metrics']:
                series = chart.series.create(property=metric['name'],
                                    label=metric['label'],
                                    color=metric['color'],
                                    type=metric['type'],
                                    aggregate=metric['agg'],
                                    left=metric['left'],
                                    order=order)

                if 'filters' in metric:
                    for filter in metric['filters']:
                        series.filters.create(field_name=filter['field'], field_value=filter['value'])

                order += 1

            return HttpResponseRedirect(reverse("dashboard"))

    class Detail(SmartListView):
        link_fields = []

        def get_stat_class_method(self, name):
            cl = self.request.REQUEST['dataset']
            d = cl.rfind(".")
            classname = cl[d+1:len(cl)]
            m = __import__(cl[0:d], globals(), locals(), [classname])
            clazz = getattr(m, classname)
            return getattr(clazz, name, None)

        def derive_title(self):
            model_class = self.request.REQUEST['dataset']
            model_cfg = Chart.get_model_config(model_class)
            return model_cfg['name']

        def derive_fields(self):
            model_class = self.request.REQUEST['dataset']
            metric = self.request.REQUEST['metric']

            custom_field_method = self.get_stat_class_method('get_detail_fields')
            if custom_field_method:
                fields = custom_field_method(metric)
            else:
                fields = [Chart.get_model_config(model_class)['date_field'], self.request.REQUEST['metric']]

            return fields

        def lookup_field_link(self, context, field, obj):
            model_class = self.request.REQUEST['dataset']
            metric = self.request.REQUEST['metric']

            custom_url_method = self.get_stat_class_method('get_detail_link_url')
            if custom_url_method:
                return custom_url_method(metric, obj, field)
            else:
                return None

        def derive_link_fields(self, context):
            model_class = self.request.REQUEST['dataset']
            metric = self.request.REQUEST['metric']

            custom_link_method = self.get_stat_class_method('get_detail_link_fields')            
            if custom_link_method:
                return custom_link_method(metric)
            else:
                return []

        def get_queryset(self, **kwargs):
            model_class = self.request.REQUEST['dataset']
            metric = self.request.REQUEST['metric']
            interval = self.request.REQUEST['interval']
            bucket = int(self.request.REQUEST['bucket'])
            filters = ChartCRUDL.get_filters(self.request)

            model_cfg = Chart.get_model_config(model_class)
            qs = Chart.get_model(model_class).objects.all()

            # apply any filters that were included
            if filters:
                for field,value in filters.iteritems():
                    qs = qs.filter(**{ field : value})

            # filter by our time series bucket
            time_series = Chart.get_series_data(model_class, metric, interval, None, filters)
            (start, rollup) = time_series[bucket]
            end = start + relativedelta(**{interval:1})

            custom_item_method = self.get_stat_class_method('get_detail_items')
            if custom_item_method:
                return custom_item_method(metric, start, end, filters)
            else:
                date_field = model_cfg['date_field']
                qs = qs.filter(**{ '%s__gte' % date_field : start, '%s__lt' % date_field : end })
                return qs

    class Series(SmartView, TemplateView):

        def get_context_data(self, **kwargs):

            context = dict()

            if 'dataset' not in self.request.REQUEST:
                raise Exception("dataset is required")

            if 'metric' not in self.request.REQUEST:
                raise Exception("metric is required")

            if 'interval' not in self.request.REQUEST:
                raise Exception("interval is required")

            if 'aggregate' not in self.request.REQUEST:
                raise Exception("aggregate is required")

            model_class = self.request.REQUEST['dataset']
            metric = self.request.REQUEST['metric']
            interval = self.request.REQUEST['interval']
            aggregate = self.request.REQUEST['aggregate']

            context['dataset'] = model_class
            context['metric'] = metric
            context['interval'] = interval
            context['aggregate'] = aggregate

            # optional data field to match up async requests
            if 'data' in self.request.REQUEST:
                context['data'] = self.request.REQUEST['data']

            date_format = '%h %d'
            if interval == 'days':
                # date_format = '%a, %h %d'
                date_format = '%h %d'
            elif interval == 'months':
                date_format = '%h %Y'
            elif interval == 'years':
                date_format = '%Y'


            filters = ChartCRUDL.get_filters(self.request)
            time_series = Chart.get_series_data(model_class, metric, interval, aggregate, filters)
            series = []
            labels = []
            for point in time_series:
                date,value = point
                if value:
                    series.append(value)
                else:
                    series.append(0)
                labels.append(date.strftime(date_format))

            context['filters'] = filters
            context['series'] = dict(data=series, labels=labels)

            return context

    class Read(SmartReadView):
        def get_context_data(self, **kwargs):
            context = super(ChartCRUDL.Read, self).get_context_data(**kwargs)
            return context

    @classmethod
    def get_filters(cls, request):
        filters = dict()
        if 'filters' in request.REQUEST:
            filter_qs = request.REQUEST['filters']
            for filter in filter_qs.split(","):
                (field, value) = filter.split(":")
                filters[field] = value
        return filters
