import random
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Sum
from .models import (
    Habitacion, Galeria, TipoHabitacion, Hotel,
    Huesped, Reserva, Pago, Servicio, ServicioReserva
)


def _parsear_fecha(valor_fecha):
    if isinstance(valor_fecha, date):
        return valor_fecha
    return datetime.strptime(str(valor_fecha), "%Y-%m-%d").date()


def _hay_cruce_fechas(habitacion, f_entrada, f_salida, excluir_reserva_id=None):
    qs = Reserva.objects.filter(
        habitacion=habitacion,
        estado__in=['PENDIENTE', 'CONFIRMADA', 'EN_ESTANCIA'],
        fecha_entrada__lt=f_salida,
        fecha_salida__gt=f_entrada,
    )
    if excluir_reserva_id:
        qs = qs.exclude(id=excluir_reserva_id)
    return qs.exists()


def _calcular_resumen_financiero_reserva(reserva):
    noches = max(1, (reserva.fecha_salida - reserva.fecha_entrada).days)
    subtotal_habitacion = Decimal(str(reserva.habitacion.precio)) * Decimal(noches)
    subtotal_servicios = Decimal('0')
    for item in reserva.servicios_asociados.select_related('servicio').all():
        subtotal_servicios += Decimal(str(item.servicio.costo)) * Decimal(item.cantidad)
    valor_total = subtotal_habitacion + subtotal_servicios
    valor_pagado = reserva.pagos.aggregate(total=Sum('monto'))['total'] or Decimal('0')
    saldo_pendiente = valor_total - Decimal(str(valor_pagado))
    if saldo_pendiente < Decimal('0'):
        saldo_pendiente = Decimal('0')
    abono_30 = (valor_total * Decimal('0.30')).quantize(Decimal('1'))
    return {
        'noches': noches,
        'valor_total': valor_total,
        'valor_pagado': Decimal(str(valor_pagado)),
        'saldo_pendiente': saldo_pendiente,
        'abono_30': abono_30,
    }


def actualizar_estados_habitaciones_por_fechas():
    hoy = date.today()
    reservas_activas = Reserva.objects.filter(estado__in=['CONFIRMADA', 'EN_ESTANCIA'])

    for res in reservas_activas:
        habitacion = res.habitacion
        f_entrada = res.fecha_entrada
        f_salida = res.fecha_salida
        f_mantenimiento_inicio = f_entrada - timedelta(days=2)

        if res.estado == 'EN_ESTANCIA' and hoy <= f_salida:
            if habitacion.estado != 'OCUPADA':
                habitacion.estado = 'OCUPADA'
                habitacion.save()
        elif f_mantenimiento_inicio <= hoy < f_entrada:
            if habitacion.estado != 'OCUPADA':
                habitacion.estado = 'MANTENIMIENTO'
                habitacion.save()
        elif f_entrada <= hoy <= f_salida:
            if habitacion.estado != 'OCUPADA':
                habitacion.estado = 'OCUPADA'
                habitacion.save()
        elif hoy > f_salida:
            if habitacion.estado in ['OCUPADA', 'MANTENIMIENTO']:
                habitacion.estado = 'DISPONIBLE'
                habitacion.save()


def es_administrador(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def es_recepcionista(user):
    return user.is_authenticated and user.is_staff


def home(request):
    context = {
        'nombre_hotel': 'Hotel Real Caribe',
        'ubicacion': 'Riohacha, La Guajira',
    }
    return render(request, 'home.html', context)


def habitaciones(request):
    actualizar_estados_habitaciones_por_fechas()
    lista_habitaciones = Habitacion.objects.all()
    context = {
        'habitaciones': lista_habitaciones,
        'ubicacion': 'Riohacha, La Guajira',
    }
    return render(request, 'habitaciones.html', context)


def login_view(request):
    if request.method == 'POST':
        usuario = request.POST.get('username')
        clave = request.POST.get('password')

        user = authenticate(request, username=usuario, password=clave)

        if user is not None:
            auth_login(request, user)
            if user.is_staff or user.is_superuser:
                return redirect('dashboard')
            else:
                return redirect('home')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


def registro_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya está en uso.')
            return redirect('registro')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Ya existe una cuenta registrada con este correo electrónico.')
            return redirect('registro')

        codigo_verificacion = str(random.randint(100000, 999999))

        request.session['registro_temp'] = {
            'username': username,
            'email': email,
            'password': password,
            'codigo': codigo_verificacion
        }

        asunto = "Código de verificación - SysHSENA (Hotel Real Caribe)"
        mensaje = f"""
        Hola,
        Has solicitado crear una cuenta en SysHSENA (Hotel Real Caribe).
        Tu código de verificación es: {codigo_verificacion}
        """

        try:
            send_mail(
                subject=asunto,
                message=mensaje,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            messages.success(request, '¡Código de verificación enviado a tu correo electrónico!')
            return redirect('verificar_codigo')
        except Exception:
            messages.error(request, 'Error al enviar el correo de verificación. Inténtalo de nuevo.')
            return redirect('registro')

    return render(request, 'registro.html')


def verificar_codigo_view(request):
    datos_temp = request.session.get('registro_temp')

    if not datos_temp:
        messages.error(request, 'No hay ningún proceso de registro activo.')
        return redirect('registro')

    if request.method == 'POST':
        codigo_ingresado = request.POST.get('codigo')

        if codigo_ingresado == datos_temp['codigo']:
            User.objects.create_user(
                username=datos_temp['username'],
                email=datos_temp['email'],
                password=datos_temp['password']
            )
            del request.session['registro_temp']
            messages.success(request, '¡Cuenta creada y verificada con éxito! Ya puedes iniciar sesión.')
            return redirect('login')
        else:
            messages.error(request, 'Código de verificación incorrecto. Inténtalo de nuevo.')

    return render(request, 'verificar_codigo.html')


def contactanos_view(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        email_cliente = request.POST.get('email')
        telefono = request.POST.get('telefono', 'No proporcionado')
        asunto_opcion = request.POST.get('asunto')
        mensaje_texto = request.POST.get('mensaje')

        asunto_email = f"Nuevo mensaje web: {asunto_opcion} - de {nombre}"
        cuerpo_mensaje = f"Cliente: {nombre}\nCorreo: {email_cliente}\nTeléfono: {telefono}\nMensaje:\n{mensaje_texto}"

        asunto_cliente = "Hemos recibido tu mensaje - Hotel Real Caribe"
        cuerpo_cliente = f"""Hola {nombre},

Hemos recibido tu mensaje referente a '{asunto_opcion}'. Nuestro equipo lo está revisando y nos pondremos en contacto contigo muy pronto a través de este medio o por teléfono.

¡Gracias por comunicarte con el Hotel Real Caribe en Riohacha, La Guajira!

Atentamente,
Servicio al Cliente - SysHSENA
"""

        try:
            send_mail(asunto_email, cuerpo_mensaje, settings.DEFAULT_FROM_EMAIL, [settings.DEFAULT_FROM_EMAIL], fail_silently=False)

            if email_cliente:
                send_mail(asunto_cliente, cuerpo_cliente, settings.DEFAULT_FROM_EMAIL, [email_cliente], fail_silently=True)

            messages.success(request, "¡Tu mensaje ha sido enviado con éxito! Te hemos enviado una confirmación a tu correo.")
        except Exception:
            messages.error(request, "Hubo un error al enviar el mensaje.")

        return redirect('contactanos')

    return render(request, 'contactanos.html')


def galeria_view(request):
    fotos = Galeria.objects.all().order_by('-fecha_subida')
    return render(request, 'galeria.html', {'fotos': fotos, 'nombre_hotel': 'Hotel Real Caribe'})


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def galeria_ad_view(request):
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        imagen = request.FILES.get('imagen')
        if imagen:
            Galeria.objects.create(titulo=titulo, imagen=imagen)
            return redirect('galeria_ad')

    fotos = Galeria.objects.all().order_by('-fecha_subida')
    return render(request, 'adminstrativo/galeria_ad.html', {'fotos': fotos})


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def eliminar_galeria_view(request, foto_id):
    foto = get_object_or_404(Galeria, id=foto_id)
    if request.method == 'POST':
        foto.delete()
    return redirect('galeria_ad')


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def dashboard_view(request):
    actualizar_estados_habitaciones_por_fechas()
    hoy = date.today()

    total_habitaciones = Habitacion.objects.count()
    habitaciones_disponibles = Habitacion.objects.filter(estado='DISPONIBLE').count()
    habitaciones_ocupadas = Habitacion.objects.filter(estado='OCUPADA').count()
    habitaciones_no_disponibles = total_habitaciones - habitaciones_disponibles
    porcentaje_ocupacion = int((habitaciones_ocupadas / total_habitaciones * 100)) if total_habitaciones > 0 else 0

    reservas_activas = Reserva.objects.filter(estado__in=['CONFIRMADA', 'EN_ESTANCIA']).count()
    reservas_del_dia = Reserva.objects.filter(creada_en__date=hoy).count()
    pagos_pendientes = Reserva.objects.filter(estado='PENDIENTE').count()
    total_huespedes = Huesped.objects.count()
    ingresos_totales = Pago.objects.aggregate(total=Sum('monto'))['total'] or 0

    usuarios_clientes = User.objects.filter(is_staff=False, is_superuser=False).count()
    usuarios_admin = User.objects.filter(is_staff=True).count()

    conteo_meses = [Reserva.objects.filter(creada_en__month=m).count() for m in range(1, 13)]

    context = {
        'total_habitaciones': total_habitaciones,
        'habitaciones_disponibles': habitaciones_disponibles,
        'habitaciones_ocupadas': habitaciones_ocupadas,
        'habitaciones_no_disponibles': habitaciones_no_disponibles,
        'porcentaje_ocupacion': porcentaje_ocupacion,
        'reservas_activas': reservas_activas,
        'reservas_del_dia': reservas_del_dia,
        'pagos_pendientes': pagos_pendientes,
        'total_huespedes': total_huespedes,
        'ingresos_totales': ingresos_totales,
        'usuarios_clientes': usuarios_clientes,
        'usuarios_admin': usuarios_admin,
        'meses_conteo_json': json.dumps(conteo_meses),
    }
    return render(request, 'adminstrativo/dashboard.html', context)


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def habitaciones_ad_view(request):
    actualizar_estados_habitaciones_por_fechas()
    habitaciones = Habitacion.objects.all().order_by('numero')
    tipos_habitacion = TipoHabitacion.objects.all()
    context = {
        'habitaciones': habitaciones,
        'tipos_habitacion': tipos_habitacion
    }
    return render(request, 'adminstrativo/habitaciones_ad.html', context)


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def crear_habitacion_view(request):
    if request.method == 'POST':
        numero = request.POST.get('numero')
        piso = request.POST.get('piso')
        tipo_id = request.POST.get('tipo_habitacion')
        capacidad = request.POST.get('capacidad')
        precio = request.POST.get('precio')
        estado = request.POST.get('estado')
        imagen = request.FILES.get('imagen')
        hotel_obj = Hotel.objects.first()
        tipo_obj = get_object_or_404(TipoHabitacion, id=tipo_id)

        Habitacion.objects.create(
            hotel=hotel_obj, numero=numero, piso=piso,
            tipo_habitacion=tipo_obj, capacidad=capacidad,
            precio=precio, estado=estado, imagen=imagen
        )
        messages.success(request, f'Habitación #{numero} creada con éxito.')
    return redirect('habitaciones_ad')


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def editar_habitacion_view(request, hab_id):
    habitacion = get_object_or_404(Habitacion, id=hab_id)
    if request.method == 'POST':
        habitacion.numero = request.POST.get('numero')
        habitacion.piso = request.POST.get('piso')
        habitacion.tipo_habitacion = get_object_or_404(TipoHabitacion, id=request.POST.get('tipo_habitacion'))
        habitacion.capacidad = request.POST.get('capacidad')
        habitacion.precio = request.POST.get('precio')
        habitacion.estado = request.POST.get('estado')
        if request.FILES.get('imagen'):
            habitacion.imagen = request.FILES.get('imagen')
        habitacion.save()
        messages.success(request, f'Habitación #{habitacion.numero} actualizada correctamente.')
        return redirect('habitaciones_ad')

    return render(request, 'adminstrativo/editar_habitacion.html', {'habitacion': habitacion, 'tipos_habitacion': TipoHabitacion.objects.all()})


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def eliminar_habitacion_view(request, hab_id):
    habitacion = get_object_or_404(Habitacion, id=hab_id)
    habitacion.delete()
    messages.success(request, 'Habitación eliminada correctamente.')
    return redirect('habitaciones_ad')


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def servicios_ad_view(request):
    if request.method == 'POST':
        habitacion_id = request.POST.get('habitacion_id')
        valor = float(request.POST.get('valor', 0))
        habitacion = get_object_or_404(Habitacion, id=habitacion_id)
        habitacion.precio = float(habitacion.precio) + valor
        habitacion.save()
        messages.success(request, f'Servicio asignado a Habitación #{habitacion.numero}.')
        return redirect('servicios_ad')

    return render(request, 'adminstrativo/servicios_ad.html', {'habitaciones': Habitacion.objects.all().order_by('numero')})


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def reservas_ad_view(request):
    actualizar_estados_habitaciones_por_fechas()
    if request.method == 'POST':
        reserva_id = request.POST.get('reserva_id')
        accion = request.POST.get('accion')
        reserva = get_object_or_404(Reserva, id=reserva_id)

        correo_cliente = None
        try:
            user_obj = User.objects.filter(id=int(reserva.huesped.numero_documento)).first()
            if user_obj and user_obj.email:
                correo_cliente = user_obj.email
        except Exception:
            pass

        if not correo_cliente and reserva.huesped and reserva.huesped.correo and reserva.huesped.correo != 'cliente@realcaribe.com':
            correo_cliente = reserva.huesped.correo

        if accion == 'aceptar':
            if _hay_cruce_fechas(reserva.habitacion, reserva.fecha_entrada, reserva.fecha_salida, excluir_reserva_id=reserva.id):
                messages.error(request, f'No se puede aceptar la reserva #{reserva.id}: existe otra reserva activa en esas fechas (RN01).')
                return redirect('reservas_ad')

            reserva.estado = 'CONFIRMADA'
            reserva.save()

            resumen = _calcular_resumen_financiero_reserva(reserva)
            metodo = request.session.pop('temp_metodo_pago_' + str(reserva.id), 'TRANSFERENCIA')
            monto_sesion = request.session.pop('temp_total_reserva_' + str(reserva.id), None)
            request.session.pop('temp_abono_reserva_' + str(reserva.id), None)

            monto_estimado = Decimal(str(monto_sesion)) if monto_sesion is not None else resumen['valor_total']
            porcentaje_abono = Decimal('0.30')
            abono_requerido = (monto_estimado * porcentaje_abono).quantize(Decimal('1'))
            saldo_restante = monto_estimado - abono_requerido

            messages.success(
                request,
                f'¡Reserva #{reserva.id} confirmada! Total: ${float(monto_estimado):,.0f} COP | Abono requerido (30%): ${float(abono_requerido):,.0f} COP por {metodo}.'
            )

            if correo_cliente:
                try:
                    send_mail(
                        subject=f"¡Reserva #{reserva.id} Aceptada! Realiza tu abono del 30% - Hotel Real Caribe",
                        message=f"""Hola {reserva.huesped.nombres},

Nos alegra informarte que tu reserva #{reserva.id} para la habitación #{reserva.habitacion.numero} ha sido ACEPTADA por administración.

Detalles de tu estadía y pago:
- Entrada: {reserva.fecha_entrada}
- Salida: {reserva.fecha_salida}
- Total de la estadía: ${float(monto_estimado):,.0f} COP
- Abono requerido (30%): ${float(abono_requerido):,.0f} COP
- Saldo restante (70%): ${float(saldo_restante):,.0f} COP
- Método de pago seleccionado: {metodo}

Por favor realiza el abono del 30% (${float(abono_requerido):,.0f} COP) mediante {metodo} para dejar tu reserva asegurada.

Atentamente,
Hotel Real Caribe""",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[correo_cliente],
                        fail_silently=False,
                    )
                except Exception as e:
                    print(f"Error enviando correo de aceptación: {e}")

        elif accion == 'cancelar':
            id_res = reserva.id
            nombre_huesped = reserva.huesped.nombres if reserva.huesped else "Cliente"

            request.session.pop('temp_metodo_pago_' + str(reserva.id), None)
            request.session.pop('temp_total_reserva_' + str(reserva.id), None)
            request.session.pop('temp_abono_reserva_' + str(reserva.id), None)
            reserva.estado = 'CANCELADA'
            reserva.save()
            reserva.delete()
            messages.warning(request, f'La reserva #{id_res} ha sido cancelada y eliminada.')

            if correo_cliente:
                try:
                    send_mail(
                        subject=f"Actualización sobre tu reserva #{id_res} - Hotel Real Caribe",
                        message=f"""Hola {nombre_huesped},

Te escribimos del Hotel Real Caribe para informarte que tu solicitud de reserva #{id_res} no ha podido ser confirmada en esta ocasión.

Si tienes dudas o deseas reprogramar, puedes contactarnos directamente.

Atentamente,
Hotel Real Caribe""",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[correo_cliente],
                        fail_silently=False,
                    )
                except Exception as e:
                    print(f"Error enviando correo de cancelación: {e}")

        return redirect('reservas_ad')

    context = {
        'reservas': Reserva.objects.all().order_by('-creada_en'),
        'usuarios_lista': User.objects.all(),
        'habitaciones_lista': Habitacion.objects.all(),
    }
    return render(request, 'adminstrativo/reservas_ad.html', context)


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def crear_reserva_ad_view(request):
    if request.method == 'POST':
        usuario_id = request.POST.get('usuario_id')
        habitacion_id = request.POST.get('habitacion_id')
        fecha_entrada_raw = request.POST.get('fecha_entrada')
        fecha_salida_raw = request.POST.get('fecha_salida')
        cantidad_huespedes = int(request.POST.get('cantidad_huespedes', 1) or 1)

        try:
            f_entrada = _parsear_fecha(fecha_entrada_raw)
            f_salida = _parsear_fecha(fecha_salida_raw)
        except (ValueError, TypeError):
            messages.error(request, 'Las fechas ingresadas no son válidas.')
            return redirect('reservas_ad')

        if f_salida <= f_entrada:
            messages.error(request, 'La fecha de salida debe ser posterior a la fecha de entrada (RN03).')
            return redirect('reservas_ad')

        usuario_obj = get_object_or_404(User, id=usuario_id)
        habitacion_obj = get_object_or_404(Habitacion, id=habitacion_id)

        if cantidad_huespedes > habitacion_obj.capacidad:
            messages.error(
                request,
                f'La cantidad de huéspedes ({cantidad_huespedes}) supera la capacidad máxima de la habitación #{habitacion_obj.numero} ({habitacion_obj.capacidad}) (RN02).'
            )
            return redirect('reservas_ad')

        if _hay_cruce_fechas(habitacion_obj, f_entrada, f_salida):
            messages.error(
                request,
                f'La habitación #{habitacion_obj.numero} ya tiene una reserva activa en ese rango de fechas (RN01).'
            )
            return redirect('reservas_ad')

        huesped, _ = Huesped.objects.get_or_create(
            numero_documento=str(usuario_obj.id),
            defaults={
                'nombres': usuario_obj.username,
                'apellidos': 'Admin',
                'telefono': '3000000000',
                'correo': usuario_obj.email or 'cliente@realcaribe.com'
            }
        )

        reserva = Reserva.objects.create(
            huesped=huesped,
            habitacion=habitacion_obj,
            fecha_entrada=f_entrada,
            fecha_salida=f_salida,
            estado='PENDIENTE'
        )
        messages.success(request, f'Reserva #{reserva.id} creada.')
    return redirect('reservas_ad')


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def pagos_ad_view(request):
    pagos = Pago.objects.select_related('reserva', 'reserva__huesped', 'reserva__habitacion').all().order_by('-fecha_pago')
    resumenes_por_reserva = {}
    for pago in pagos:
        if pago.reserva_id not in resumenes_por_reserva:
            resumenes_por_reserva[pago.reserva_id] = _calcular_resumen_financiero_reserva(pago.reserva)
    return render(request, 'adminstrativo/pagos_ad.html', {
        'pagos': pagos,
        'resumenes_por_reserva': resumenes_por_reserva,
    })


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def editar_pago_view(request, pago_id):
    pago = get_object_or_404(Pago, id=pago_id)
    if request.method == 'POST':
        pago.monto = request.POST.get('monto')
        pago.metodo = request.POST.get('metodo')
        pago.save()
        messages.success(request, 'Pago actualizado.')
        return redirect('pagos_ad')
    return render(request, 'adminstrativo/editar_pago.html', {'pago': pago})


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def eliminar_pago_view(request, pago_id):
    if request.method == 'POST':
        get_object_or_404(Pago, id=pago_id).delete()
        messages.success(request, 'Pago eliminado.')
    return redirect('pagos_ad')


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def devolver_dinero_view(request, pago_id):
    if request.method == 'POST':
        get_object_or_404(Pago, id=pago_id).delete()
        messages.success(request, 'Devolución procesada.')
    return redirect('pagos_ad')


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def imprimir_factura_view(request, pago_id):
    pago = get_object_or_404(Pago, id=pago_id)
    resumen = _calcular_resumen_financiero_reserva(pago.reserva)
    return render(request, 'adminstrativo/factura_print.html', {
        'pago': pago,
        'reserva': pago.reserva,
        'huesped': pago.reserva.huesped,
        'habitacion': pago.reserva.habitacion,
        'valor_total_reserva': resumen['valor_total'],
        'valor_pagado_reserva': resumen['valor_pagado'],
        'saldo_pendiente_reserva': resumen['saldo_pendiente'],
    })


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def reportes_ad_view(request):
    actualizar_estados_habitaciones_por_fechas()

    fecha_desde_str = request.GET.get('fecha_desde', '').strip()
    fecha_hasta_str = request.GET.get('fecha_hasta', '').strip()
    estado_filtro = request.GET.get('estado', '').strip()
    habitacion_filtro = request.GET.get('habitacion', '').strip()
    huesped_filtro = request.GET.get('huesped', '').strip()

    reservas_qs = Reserva.objects.select_related('huesped', 'habitacion', 'habitacion__tipo_habitacion').order_by('-creada_en')

    f_desde = None
    f_hasta = None
    if fecha_desde_str:
        try:
            f_desde = _parsear_fecha(fecha_desde_str)
            reservas_qs = reservas_qs.filter(fecha_entrada__gte=f_desde)
        except ValueError:
            messages.warning(request, 'Fecha "desde" no válida.')

    if fecha_hasta_str:
        try:
            f_hasta = _parsear_fecha(fecha_hasta_str)
            reservas_qs = reservas_qs.filter(fecha_salida__lte=f_hasta)
        except ValueError:
            messages.warning(request, 'Fecha "hasta" no válida.')

    if estado_filtro:
        reservas_qs = reservas_qs.filter(estado=estado_filtro)

    if habitacion_filtro:
        reservas_qs = reservas_qs.filter(habitacion_id=habitacion_filtro)

    if huesped_filtro:
        reservas_qs = reservas_qs.filter(huesped_id=huesped_filtro)

    total_habitaciones = Habitacion.objects.count()
    habitaciones_ocupadas = Habitacion.objects.filter(estado='OCUPADA').count()
    habitaciones_disponibles = Habitacion.objects.filter(estado='DISPONIBLE').count()
    porcentaje_ocupacion = round((habitaciones_ocupadas / total_habitaciones * 100), 1) if total_habitaciones > 0 else 0

    pagos_qs = Pago.objects.select_related('reserva', 'reserva__huesped', 'reserva__habitacion').order_by('-fecha_pago')
    if f_desde:
        pagos_qs = pagos_qs.filter(fecha_pago__date__gte=f_desde)
    if f_hasta:
        pagos_qs = pagos_qs.filter(fecha_pago__date__lte=f_hasta)

    total_recaudado = pagos_qs.aggregate(total=Sum('monto'))['total'] or Decimal('0')

    saldos_pendientes_lista = []
    total_saldos_pendientes = Decimal('0')
    for res in Reserva.objects.select_related('huesped', 'habitacion').prefetch_related('pagos', 'servicios_asociados__servicio').all():
        info = _calcular_resumen_financiero_reserva(res)
        if info['saldo_pendiente'] > Decimal('0'):
            total_saldos_pendientes += info['saldo_pendiente']
            saldos_pendientes_lista.append({
                'reserva': res,
                'valor_total': info['valor_total'],
                'valor_pagado': info['valor_pagado'],
                'saldo_pendiente': info['saldo_pendiente'],
            })

    if f_desde and f_hasta:
        periodo_seleccionado = f"{f_desde} al {f_hasta}"
    elif f_desde:
        periodo_seleccionado = f"Desde {f_desde}"
    elif f_hasta:
        periodo_seleccionado = f"Hasta {f_hasta}"
    else:
        periodo_seleccionado = "Todo el historial"

    huespedes_qs = Huesped.objects.prefetch_related('reserva_set__habitacion').order_by('nombres', 'apellidos')

    context = {
        'ingresos_totales': Pago.objects.aggregate(Sum('monto'))['monto__sum'] or 0,
        'total_reservas_realizadas': Reserva.objects.count(),
        'total_pagos_registrados': Pago.objects.count(),
        'pagos_efectivo': Pago.objects.filter(metodo='EFECTIVO').aggregate(Sum('monto'))['monto__sum'] or 0,
        'pagos_tarjeta': Pago.objects.filter(metodo='TARJETA').aggregate(Sum('monto'))['monto__sum'] or 0,
        'pagos_transferencia': Pago.objects.filter(metodo='TRANSFERENCIA').aggregate(Sum('monto'))['monto__sum'] or 0,
        'reservas_filtradas': reservas_qs,
        'habitaciones_filtro': Habitacion.objects.all().order_by('numero'),
        'huespedes_filtro': Huesped.objects.all().order_by('nombres'),
        'estados_reserva': Reserva.ESTADOS_RESERVA,
        'filtros_actuales': {
            'fecha_desde': fecha_desde_str,
            'fecha_hasta': fecha_hasta_str,
            'estado': estado_filtro,
            'habitacion': habitacion_filtro,
            'huesped': huesped_filtro,
        },
        'total_habitaciones': total_habitaciones,
        'habitaciones_ocupadas': habitaciones_ocupadas,
        'habitaciones_disponibles': habitaciones_disponibles,
        'porcentaje_ocupacion': porcentaje_ocupacion,
        'pagos_filtrados': pagos_qs,
        'total_recaudado': total_recaudado,
        'total_saldos_pendientes': total_saldos_pendientes,
        'saldos_pendientes_lista': saldos_pendientes_lista,
        'periodo_seleccionado': periodo_seleccionado,
        'huespedes_reporte': huespedes_qs,
    }
    return render(request, 'adminstrativo/reportes_ad.html', context)


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def configuracion_ad_view(request):
    return render(request, 'adminstrativo/configuracion_ad.html')


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def lista_usuarios_view(request):
    return render(request, 'adminstrativo/lista_usuarios.html', {'usuarios': User.objects.all().order_by('-date_joined')})


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def crear_usuario_view(request):
    if request.method == 'POST':
        u = User.objects.create_user(
            username=request.POST.get('username'),
            email=request.POST.get('email'),
            password=request.POST.get('password')
        )
        if request.POST.get('es_staff') == 'on':
            u.is_staff = True
            u.save()
        messages.success(request, 'Usuario creado con éxito.')
        return redirect('lista_usuarios')
    return render(request, 'adminstrativo/crear_usuario.html')


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def cambiar_rol_usuario_view(request, user_id):
    u = get_object_or_404(User, id=user_id)
    if u != request.user:
        u.is_staff = not u.is_staff
        u.save()
        messages.success(request, 'Rol actualizado.')
    return redirect('lista_usuarios')


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def eliminar_usuario_view(request, user_id):
    u = get_object_or_404(User, id=user_id)
    if u != request.user:
        u.delete()
        messages.success(request, 'Usuario eliminado.')
    return redirect('lista_usuarios')


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def toggle_estado_usuario_view(request, user_id):
    u = get_object_or_404(User, id=user_id)
    if u != request.user:
        u.is_active = not u.is_active
        u.save()
    return redirect('lista_usuarios')


@login_required(login_url='login')
@user_passes_test(es_administrador, login_url='home')
def editar_usuario_view(request, user_id):
    usuario = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        usuario.username = request.POST.get('username')
        usuario.email = request.POST.get('email')
        if request.POST.get('password'):
            usuario.set_password(request.POST.get('password'))
        usuario.save()
        messages.success(request, 'Usuario actualizado.')
        return redirect('lista_usuarios')
    return render(request, 'adminstrativo/editar_usuario.html', {'usuario_edit': usuario})


# ==========================================
# --- VISTAS DE MOSTRADOR (RECEPCIÓN) ---
# ==========================================

@login_required(login_url='login')
def recepcion_registrar_huesped_view(request):
    if request.method == 'POST':
        nombres = request.POST.get('nombres')
        apellidos = request.POST.get('apellidos')
        documento = request.POST.get('numero_documento')
        telefono = request.POST.get('telefono')
        correo = request.POST.get('correo')

        Huesped.objects.get_or_create(
            numero_documento=documento,
            defaults={'nombres': nombres, 'apellidos': apellidos, 'telefono': telefono, 'correo': correo}
        )
        messages.success(request, f'Huésped {nombres} {apellidos} registrado correctamente en mostrador.')
        return redirect('recepcion_registrar_huesped')

    huespedes = Huesped.objects.all().order_by('-id')
    return render(request, 'adminstrativo/registrar_huesped.html', {'huespedes': huespedes})


@login_required(login_url='login')
def recepcion_reservas_view(request):
    actualizar_estados_habitaciones_por_fechas()
    context = {
        'reservas': Reserva.objects.all().order_by('-creada_en'),
        'habitaciones': Habitacion.objects.filter(estado='DISPONIBLE'),
    }
    return render(request, 'adminstrativo/reservas_recepcion.html', context)


@login_required(login_url='login')
def recepcion_crear_reserva_view(request):
    if request.method == 'POST':
        doc = request.POST.get('numero_documento')
        nombres = request.POST.get('nombres')
        apellidos = request.POST.get('apellidos')
        telefono = request.POST.get('telefono')
        correo = request.POST.get('correo')
        habitacion_id = request.POST.get('habitacion_id')
        fecha_entrada_raw = request.POST.get('fecha_entrada')
        fecha_salida_raw = request.POST.get('fecha_salida')
        cantidad_huespedes = int(request.POST.get('cantidad_huespedes', 1) or 1)

        try:
            f_entrada = _parsear_fecha(fecha_entrada_raw)
            f_salida = _parsear_fecha(fecha_salida_raw)
        except (ValueError, TypeError):
            messages.error(request, 'Las fechas ingresadas no son válidas.')
            return redirect('recepcion_crear_reserva')

        if f_salida <= f_entrada:
            messages.error(request, 'La fecha de salida debe ser posterior a la fecha de entrada (RN03).')
            return redirect('recepcion_crear_reserva')

        habitacion = get_object_or_404(Habitacion, id=habitacion_id)

        if cantidad_huespedes > habitacion.capacidad:
            messages.error(
                request,
                f'El número de huéspedes ({cantidad_huespedes}) supera la capacidad de la habitación #{habitacion.numero} ({habitacion.capacidad}) (RN02).'
            )
            return redirect('recepcion_crear_reserva')

        if _hay_cruce_fechas(habitacion, f_entrada, f_salida):
            messages.error(
                request,
                f'La habitación #{habitacion.numero} ya tiene una reserva activa en ese rango de fechas (RN01).'
            )
            return redirect('recepcion_crear_reserva')

        huesped, _ = Huesped.objects.get_or_create(
            numero_documento=doc,
            defaults={'nombres': nombres, 'apellidos': apellidos, 'telefono': telefono, 'correo': correo}
        )

        reserva = Reserva.objects.create(
            huesped=huesped,
            habitacion=habitacion,
            fecha_entrada=f_entrada,
            fecha_salida=f_salida,
            estado='CONFIRMADA'
        )

        habitacion.estado = 'OCUPADA'
        habitacion.save()

        messages.success(request, f'Reserva #{reserva.id} creada y confirmada en mostrador. Registra el pago en el módulo de Pagos.')
        return redirect('recepcion_reservas')

    context = {
        'habitaciones': Habitacion.objects.filter(estado='DISPONIBLE')
    }
    return render(request, 'adminstrativo/crear_reserva.html', context)


@login_required(login_url='login')
def modificar_reserva_view(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    if request.method == 'POST':
        fecha_entrada_raw = request.POST.get('fecha_entrada')
        fecha_salida_raw = request.POST.get('fecha_salida')
        nuevo_estado = request.POST.get('estado')
        cantidad_huespedes = int(request.POST.get('cantidad_huespedes', 1) or 1)

        try:
            f_entrada = _parsear_fecha(fecha_entrada_raw)
            f_salida = _parsear_fecha(fecha_salida_raw)
        except (ValueError, TypeError):
            messages.error(request, 'Las fechas ingresadas no son válidas.')
            return redirect('modificar_reserva', reserva_id=reserva.id)

        if f_salida <= f_entrada:
            messages.error(request, 'La fecha de salida debe ser posterior a la fecha de entrada (RN03).')
            return redirect('modificar_reserva', reserva_id=reserva.id)

        huesped_id = request.POST.get('huesped_id')
        habitacion_id = request.POST.get('habitacion_id')
        habitacion_objetivo = get_object_or_404(Habitacion, id=habitacion_id) if habitacion_id else reserva.habitacion

        if cantidad_huespedes > habitacion_objetivo.capacidad:
            messages.error(
                request,
                f'El número de huéspedes ({cantidad_huespedes}) supera la capacidad de la habitación #{habitacion_objetivo.numero} ({habitacion_objetivo.capacidad}) (RN02).'
            )
            return redirect('modificar_reserva', reserva_id=reserva.id)

        if nuevo_estado in ['PENDIENTE', 'CONFIRMADA', 'EN_ESTANCIA']:
            if _hay_cruce_fechas(habitacion_objetivo, f_entrada, f_salida, excluir_reserva_id=reserva.id):
                messages.error(
                    request,
                    f'La habitación #{habitacion_objetivo.numero} ya tiene una reserva activa en ese rango de fechas (RN01).'
                )
                return redirect('modificar_reserva', reserva_id=reserva.id)

        reserva.fecha_entrada = f_entrada
        reserva.fecha_salida = f_salida
        reserva.estado = nuevo_estado

        if huesped_id:
            reserva.huesped = get_object_or_404(Huesped, id=huesped_id)

        if reserva.habitacion != habitacion_objetivo:
            reserva.habitacion.estado = 'DISPONIBLE'
            reserva.habitacion.save()

            habitacion_objetivo.estado = 'OCUPADA' if reserva.estado in ['CONFIRMADA', 'EN_ESTANCIA'] else 'DISPONIBLE'
            habitacion_objetivo.save()

            reserva.habitacion = habitacion_objetivo
        elif reserva.estado in ['CONFIRMADA', 'EN_ESTANCIA']:
            reserva.habitacion.estado = 'OCUPADA'
            reserva.habitacion.save()
        elif reserva.estado in ['FINALIZADA', 'CANCELADA']:
            reserva.habitacion.estado = 'DISPONIBLE'
            reserva.habitacion.save()

        reserva.save()
        messages.success(request, f'Reserva #{reserva.id} actualizada con éxito sin alterar datos del huésped.')
        return redirect('recepcion_reservas')

    context = {
        'reserva': reserva,
        'huespedes': Huesped.objects.all(),
        'habitaciones': Habitacion.objects.all(),
    }
    return render(request, 'adminstrativo/modificar_reserva.html', context)


@login_required(login_url='login')
def recepcion_disponibilidad_view(request):
    actualizar_estados_habitaciones_por_fechas()
    habitaciones = Habitacion.objects.all().order_by('numero')
    return render(request, 'adminstrativo/disponibilidad_recepcion.html', {'habitaciones': habitaciones})


@login_required(login_url='login')
def recepcion_checkin_checkout_view(request):
    actualizar_estados_habitaciones_por_fechas()
    context = {
        'reservas_por_llegar': Reserva.objects.filter(estado__in=['PENDIENTE', 'CONFIRMADA']),
        'estancias_activas': Reserva.objects.filter(estado='EN_ESTANCIA'),
    }
    return render(request, 'adminstrativo/gestion_checkin_checkout.html', context)


@login_required(login_url='login')
def procesar_checkin(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    if request.method == 'POST':
        if reserva.estado in ['CANCELADA', 'FINALIZADA']:
            messages.error(request, f'No se puede realizar check-in sobre una reserva en estado {reserva.estado} (RN05).')
            return redirect('recepcion_checkin_checkout')

        if _hay_cruce_fechas(reserva.habitacion, reserva.fecha_entrada, reserva.fecha_salida, excluir_reserva_id=reserva.id):
            messages.error(request, f'La habitación #{reserva.habitacion.numero} tiene otra reserva activa en estas fechas (RN01).')
            return redirect('recepcion_checkin_checkout')

        reserva.estado = 'EN_ESTANCIA'
        reserva.save()
        reserva.habitacion.estado = 'OCUPADA'
        reserva.habitacion.save()
        messages.success(request, f'Check-in realizado con éxito para la reserva #{reserva.id}. Habitación #{reserva.habitacion.numero} OCUPADA.')
    return redirect('recepcion_checkin_checkout')


@login_required(login_url='login')
def procesar_checkout(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    if request.method == 'POST':
        if reserva.estado != 'EN_ESTANCIA':
            messages.error(
                request,
                f'No se puede realizar check-out de la reserva #{reserva.id} porque no tiene check-in activo (estado actual: {reserva.estado}) (RN06).'
            )
            return redirect('recepcion_checkin_checkout')

        reserva.estado = 'FINALIZADA'
        reserva.save()
        reserva.habitacion.estado = 'DISPONIBLE'
        reserva.habitacion.save()
        messages.success(request, f'Check-out realizado. Habitación #{reserva.habitacion.numero} DISPONIBLE.')
    return redirect('recepcion_checkin_checkout')


@login_required(login_url='login')
def recepcion_pagos_view(request):
    if request.method == 'POST':
        reserva_id = request.POST.get('reserva_id')
        monto_limpio = ''.join(ch for ch in str(request.POST.get('monto', '0') or '0') if ch.isdigit())
        monto = Decimal(monto_limpio or '0')
        metodo_pago = request.POST.get('metodo_pago')

        reserva = get_object_or_404(Reserva, id=reserva_id)
        if monto <= Decimal('0'):
            messages.error(request, 'El monto del pago debe ser mayor a cero (RN08).')
            return redirect('recepcion_pagos')

        Pago.objects.create(reserva=reserva, monto=monto, metodo=metodo_pago)
        resumen = _calcular_resumen_financiero_reserva(reserva)
        messages.success(
            request,
            f'Pago de ${float(monto):,.0f} COP registrado. Total: ${float(resumen["valor_total"]):,.0f} | Abono (30%): ${float(resumen["abono_30"]):,.0f} | Pagado: ${float(resumen["valor_pagado"]):,.0f} | Saldo pendiente: ${float(resumen["saldo_pendiente"]):,.0f} COP (RN08).'
        )
        return redirect('recepcion_pagos')

    reservas_activas = Reserva.objects.filter(estado__in=['PENDIENTE', 'CONFIRMADA', 'EN_ESTANCIA']).select_related('huesped', 'habitacion').prefetch_related('pagos', 'servicios_asociados__servicio')
    reservas_detalle = []
    for r in reservas_activas:
        info = _calcular_resumen_financiero_reserva(r)
        reservas_detalle.append({
            'reserva': r,
            'valor_total': info['valor_total'],
            'abono_30': info['abono_30'],
            'valor_pagado': info['valor_pagado'],
            'saldo_pendiente': info['saldo_pendiente'],
        })
    context = {
        'reservas_activas': reservas_activas,
        'reservas_detalle': reservas_detalle,
    }
    return render(request, 'adminstrativo/registrar_pago_recepcion.html', context)


@login_required(login_url='login')
def recepcion_servicios_view(request):
    return render(request, 'adminstrativo/servicios_ad.html', {'habitaciones': Habitacion.objects.all()})


# ==========================================
# --- VISTA DE RESERVAS WEB (CLIENTES) ---
# ==========================================

@login_required(login_url='login')
def reservas_view(request):
    actualizar_estados_habitaciones_por_fechas()
    habitacion_id = request.GET.get('habitacion')
    habitacion_seleccionada = None

    if habitacion_id:
        habitacion_seleccionada = get_object_or_404(Habitacion, id=habitacion_id)

    if request.method == 'POST':
        hab_id = request.POST.get('habitacion')
        fecha_entrada_raw = request.POST.get('fecha_entrada')
        fecha_salida_raw = request.POST.get('fecha_salida')
        metodo_pago = request.POST.get('metodo_pago', 'TRANSFERENCIA')
        servicios_seleccionados = request.POST.getlist('servicios_extra')
        cantidad_huespedes = int(request.POST.get('cantidad_huespedes', 1) or 1)

        if metodo_pago not in ['TRANSFERENCIA', 'TARJETA']:
            messages.error(request, 'Solo se permiten pagos por Transferencia Bancaria o Tarjeta.')
            return redirect('reservas')

        habitacion = get_object_or_404(Habitacion, id=hab_id)

        try:
            f_entrada = _parsear_fecha(fecha_entrada_raw)
            f_salida = _parsear_fecha(fecha_salida_raw)
        except (ValueError, TypeError):
            messages.error(request, 'Por favor ingresa fechas válidas de entrada y salida.')
            return redirect('reservas')

        if f_salida <= f_entrada:
            messages.error(request, 'La fecha de salida debe ser posterior a la fecha de entrada (RN03).')
            return redirect('reservas')

        if cantidad_huespedes > habitacion.capacidad:
            messages.error(
                request,
                f'El número de huéspedes ({cantidad_huespedes}) supera la capacidad máxima de la habitación #{habitacion.numero} ({habitacion.capacidad}) (RN02).'
            )
            return redirect('reservas')

        if _hay_cruce_fechas(habitacion, f_entrada, f_salida):
            messages.error(
                request,
                f'La habitación #{habitacion.numero} no está disponible para las fechas seleccionadas porque ya tiene otra reserva activa (RN01).'
            )
            return redirect('reservas')

        noches = max(1, (f_salida - f_entrada).days)
        precio_total_estadia = float(habitacion.precio) * noches

        precios_servicios = {
            'Salón de Eventos (150000)': 150000,
            'Desayuno Caribeño (20000)': 20000,
            'Almuerzo Ejecutivo (35000)': 35000,
            'Servicio de Lavandería (25000)': 25000,
            'Minibar (30000)': 30000
        }

        for servicio in servicios_seleccionados:
            precio_total_estadia += precios_servicios.get(servicio, 0)

        abono_requerido = round(precio_total_estadia * 0.30)

        correo_usuario_registro = request.user.email if request.user.email else 'cliente@realcaribe.com'

        huesped, _ = Huesped.objects.get_or_create(
            numero_documento=str(request.user.id),
            defaults={
                'nombres': request.user.username,
                'apellidos': 'Cliente Web',
                'telefono': '3000000000',
                'correo': correo_usuario_registro
            }
        )

        if huesped.correo != correo_usuario_registro:
            huesped.correo = correo_usuario_registro
            huesped.save()

        reserva = Reserva.objects.create(
            huesped=huesped,
            habitacion=habitacion,
            fecha_entrada=f_entrada,
            fecha_salida=f_salida,
            estado='PENDIENTE'
        )

        for servicio_etiqueta in servicios_seleccionados:
            costo_srv = Decimal(str(precios_servicios.get(servicio_etiqueta, 0)))
            servicio_obj, _ = Servicio.objects.get_or_create(
                nombre=servicio_etiqueta,
                defaults={'costo': costo_srv}
            )
            ServicioReserva.objects.create(
                reserva=reserva,
                servicio=servicio_obj,
                cantidad=1
            )

        request.session['temp_metodo_pago_' + str(reserva.id)] = metodo_pago
        request.session['temp_total_reserva_' + str(reserva.id)] = precio_total_estadia
        request.session['temp_abono_reserva_' + str(reserva.id)] = abono_requerido

        if correo_usuario_registro and correo_usuario_registro != 'cliente@realcaribe.com':
            try:
                send_mail(
                    subject=f"Solicitud de Reserva #{reserva.id} Recibida - Hotel Real Caribe",
                    message=f"""Hola {huesped.nombres},

Tu solicitud de reserva #{reserva.id} para la habitación #{habitacion.numero} ha sido registrada con éxito y se encuentra en estado PENDIENTE de revisión por parte de la administración del Hotel Real Caribe.

Una vez sea aceptada, deberás abonar el 30% (${abono_requerido:,.0f} COP) mediante {metodo_pago}.

Te notificaremos tan pronto sea aceptada.

¡Gracias por preferirnos!""",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[correo_usuario_registro],
                    fail_silently=False,
                )
            except Exception as e:
                print(f"Error enviando correo de solicitud al cliente: {e}")

        messages.success(
            request,
            f'¡Solicitud de reserva #{reserva.id} enviada por ${precio_total_estadia:,.0f} COP! Al ser aceptada deberás abonar el 30% (${abono_requerido:,.0f} COP) por {metodo_pago}.'
        )
        return redirect('habitaciones')

    context = {
        'habitaciones': Habitacion.objects.filter(estado='DISPONIBLE'),
        'habitacion_seleccionada': habitacion_seleccionada,
    }
    return render(request, 'reservas.html', context)