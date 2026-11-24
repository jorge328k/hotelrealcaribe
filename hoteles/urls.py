from django.urls import path
from . import views

urlpatterns = [
    # Rutas Públicas y Generales
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('habitaciones/', views.habitaciones, name='habitaciones'),
    path('contactanos/', views.contactanos_view, name='contactanos'),
    path('galeria/', views.galeria_view, name='galeria'),
    path('registro/', views.registro_view, name='registro'),
    path('reservas/', views.reservas_view, name='reservas'),

    # --- MÓDULO DE ADMINISTRACIÓN GENERAL ---
    path('galeria/administrar/', views.galeria_ad_view, name='galeria_ad'),
    path('galeria/eliminar/<int:foto_id>/', views.eliminar_galeria_view, name='eliminar_galeria'),
    path('administracion/dashboard/', views.dashboard_view, name='dashboard'),
    path('administracion/habitaciones/', views.habitaciones_ad_view, name='habitaciones_ad'),
    path('administracion/habitaciones/crear/', views.crear_habitacion_view, name='crear_habitacion'),
    path('administracion/habitaciones/editar/<int:hab_id>/', views.editar_habitacion_view, name='editar_habitacion'),
    path('administracion/habitaciones/eliminar/<int:hab_id>/', views.eliminar_habitacion_view, name='eliminar_habitacion'),
    path('administracion/servicios/', views.servicios_ad_view, name='servicios_ad'),
    path('administracion/reservas/', views.reservas_ad_view, name='reservas_ad'),
    path('administracion/reservas/crear/', views.crear_reserva_ad_view, name='crear_reserva_ad'),
    path('administracion/pagos/', views.pagos_ad_view, name='pagos_ad'),
    path('administracion/pagos/editar/<int:pago_id>/', views.editar_pago_view, name='editar_pago'),
    path('administracion/pagos/eliminar/<int:pago_id>/', views.eliminar_pago_view, name='eliminar_pago'),
    path('pagos/devolver/<int:pago_id>/', views.devolver_dinero_view, name='devolver_dinero'),
    path('administracion/pagos/factura/<int:pago_id>/', views.imprimir_factura_view, name='imprimir_factura'),
    path('administracion/reportes/', views.reportes_ad_view, name='reportes_ad'),
    path('administracion/configuracion/', views.configuracion_ad_view, name='configuracion_ad'),

    # --- MÓDULOS DE MOSTRADOR (RECEPCIÓN) ---
    path('recepcion/registrar-huesped/', views.recepcion_registrar_huesped_view, name='recepcion_registrar_huesped'),
    path('recepcion/reservas/', views.recepcion_reservas_view, name='recepcion_reservas'),
    path('recepcion/reservas/crear/', views.recepcion_crear_reserva_view, name='recepcion_crear_reserva'),
    path('recepcion/reservas/modificar/<int:reserva_id>/', views.modificar_reserva_view, name='modificar_reserva'),
    path('recepcion/disponibilidad/', views.recepcion_disponibilidad_view, name='recepcion_disponibilidad'),
    path('recepcion/checkin-checkout/', views.recepcion_checkin_checkout_view, name='recepcion_checkin_checkout'),
    path('recepcion/checkin/<int:reserva_id>/', views.procesar_checkin, name='procesar_checkin'),
    path('recepcion/checkout/<int:reserva_id>/', views.procesar_checkout, name='procesar_checkout'),
    path('recepcion/pagos/', views.recepcion_pagos_view, name='recepcion_pagos'),
    path('recepcion/servicios/', views.recepcion_servicios_view, name='recepcion_servicios'),

    # Gestión de Usuarios
    path('usuarios/', views.lista_usuarios_view, name='lista_usuarios'),
    path('usuarios/crear/', views.crear_usuario_view, name='crear_usuario'),
    path('usuarios/rol/<int:user_id>/', views.cambiar_rol_usuario_view, name='cambiar_rol_usuario'),
    path('usuarios/eliminar/<int:user_id>/', views.eliminar_usuario_view, name='eliminar_usuario'),
    path('usuarios/estado/<int:user_id>/', views.toggle_estado_usuario_view, name='toggle_estado_usuario'),
    path('usuarios/editar/<int:user_id>/', views.editar_usuario_view, name='editar_usuario'),
]