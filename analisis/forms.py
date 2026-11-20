"""Formulario para analizar un CV."""

from django import forms

from services.extraccion import TAMANO_MAXIMO_BYTES

CLASES_TEXTAREA = (
    "block w-full rounded-lg border border-slate-300 bg-white p-3 text-sm shadow-sm "
    "focus:border-marca-500 focus:ring-2 focus:ring-marca-100 focus:outline-none"
)
CLASES_ARCHIVO = (
    "block w-full cursor-pointer rounded-lg border border-slate-300 bg-white text-sm text-slate-600 "
    "file:mr-4 file:cursor-pointer file:border-0 file:bg-marca-50 file:px-4 file:py-2.5 "
    "file:font-semibold file:text-marca-700 hover:file:bg-marca-100"
)


class AnalisisForm(forms.Form):
    """El CV llega como archivo O como texto (exactamente uno). La vacante pegada es opcional."""

    archivo_cv = forms.FileField(
        required=False,
        label="Sube tu CV",
        help_text="PDF o DOCX, máximo 5 MB. El archivo no se guarda.",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.docx", "class": CLASES_ARCHIVO}),
    )
    texto_cv = forms.CharField(
        required=False,
        label="…o pega el texto de tu CV",
        widget=forms.Textarea(attrs={"rows": 8, "class": CLASES_TEXTAREA, "placeholder": "Experiencia, habilidades, educación…"}),
    )
    texto_vacante = forms.CharField(
        required=False,
        label="Vacante que te interesa (opcional)",
        help_text="Pega la descripción de una vacante real para saber qué tan bien encajas.",
        widget=forms.Textarea(attrs={"rows": 6, "class": CLASES_TEXTAREA, "placeholder": "Título, requisitos, deseables…"}),
    )

    def clean_archivo_cv(self):
        archivo = self.cleaned_data.get("archivo_cv")
        if archivo and archivo.size > TAMANO_MAXIMO_BYTES:
            raise forms.ValidationError("El archivo pesa más de 5 MB.")
        return archivo

    def clean(self):
        datos = super().clean()
        tiene_archivo = bool(datos.get("archivo_cv"))
        tiene_texto = bool((datos.get("texto_cv") or "").strip())
        if not tiene_archivo and not tiene_texto and not self.errors:
            raise forms.ValidationError("Sube tu CV en PDF o DOCX, o pega su texto.")
        if tiene_archivo and tiene_texto:
            raise forms.ValidationError("Elige solo una opción: sube el archivo o pega el texto, no ambos.")
        return datos
