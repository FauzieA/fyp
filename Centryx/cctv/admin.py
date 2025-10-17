from django.contrib import admin

from .models import CCTV, Brand, CCTVModel


class CCTVInline(admin.TabularInline):
    model = CCTV
    extra = 0
    fields = ('identifier', 'location')
    readonly_fields = ('identifier',)


class CCTVModelInline(admin.TabularInline):
    model = CCTVModel
    extra = 0
    fields = ('name', 'brand')
    readonly_fields = ('name',)


@admin.register(CCTVModel)
class CCTVModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand')
    search_fields = ('name', 'brand__name')
    inlines = [CCTVInline]


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    inlines = [CCTVModelInline]


@admin.register(CCTV)
class CCTVAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'model', 'location')
    search_fields = ('identifier', 'model__name', 'model__brand__name')
    list_filter = ('model__brand',)
