from django import forms

class CityForm(forms.Form):
    city_name = forms.CharField(label='Enter a city in British Columbia:', max_length=100)
