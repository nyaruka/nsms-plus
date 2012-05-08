from django.conf.urls.defaults import patterns, include, url
from .views import ChartCRUDL, ReportCRUDL

urlpatterns = ChartCRUDL().as_urlpatterns()
urlpatterns += ReportCRUDL().as_urlpatterns()
