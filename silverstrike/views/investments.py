from datetime import date

from dateutil.relativedelta import relativedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic

from silverstrike.lib import last_day_of_month


class InvestmentView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'silverstrike/investments.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'investments'
        
        return context
