from django import forms

class UploadVieuxRainfallReport(forms.Form):
    file = forms.FileField()