from django import forms


class StyledFormMixin:
    """Automatically add .form-control to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if "class" in field.widget.attrs:
                field.widget.attrs["class"] += " form-control"
            else:
                field.widget.attrs["class"] = "form-control"

            if "placeholder" not in field.widget.attrs:
                field.widget.attrs["placeholder"] = field.label
