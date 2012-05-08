from django.core.urlresolvers import reverse
from rapidsms.models import Backend, Connection
from smartmin.tests import _CRUDLTest
from nsms.tests import NSMSTest

class ChartCRUDLTest(_CRUDLTest):
    def setUp(self):
        self.crudl = ChartCRUDL
        self.user = self.create_user('billg', ['Administrators'])

    def getUser(self):
        return self.user

    def getCreatePostData(self):
        return dict(interval='weeks', model_class='malaria.models.MalariaReport', title='My First Chart')

    def getUpdatePostData(self):
        update_dict = self.getCreatePostData()
        update_dict['interval'] = 'months'
        return update_dict

    def testDataset(self):
        self.do_test_view('dataset')

class ReportCRUDLTest(_CRUDLTest):
    def setUp(self):
        self.crudl = ReportCRUDL
        self.user = self.create_user('billg', ['Administrators'])

    def getUser(self):
        return self.user

    def getCreatePostData(self):
        return dict(name="report name", description="report description")

    def getUpdatePostData(self):
        update_dict = self.getCreatePostData()
        update_dict['name'] = 'updated report name'
        return update_dict
