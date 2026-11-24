from django.db import models

class Rol(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

class Usuario(models.Model):
    nombre = models.CharField(max_length=100)
    correo = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    rol = models.ForeignKey(Rol, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.nombre} ({self.rol.nombre})"

class Hotel(models.Model):
    nombre = models.CharField(max_length=150, default="Hotel Real Caribe")
    descripcion = models.TextField()
    direccion = models.CharField(max_length=150, default="Calle 12 #7-45")
    municipio = models.CharField(max_length=50, default="Riohacha")
    telefono = models.CharField(max_length=20)
    correo = models.EmailField()

    def __str__(self):
        return self.nombre

class TipoHabitacion(models.Model):
    nombre = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True, null=True)
    precio_base = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.nombre

class Habitacion(models.Model):
    ESTADOS = [
        ('DISPONIBLE', 'Disponible'),
        ('OCUPADA', 'Ocupada'),
        ('MANTENIMIENTO', 'En Mantenimiento/Reparación'),
    ]
    
    MODALIDAD_CHOICES = [
        ('DIA', 'Por Día'),
        ('NOCHE', 'Por Noche'),
        ('DIAS', 'Por Varios Días'),
    ]

    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE)
    numero = models.CharField(max_length=10, unique=True)
    piso = models.IntegerField()
    tipo_habitacion = models.ForeignKey(TipoHabitacion, on_delete=models.CASCADE)
    capacidad = models.IntegerField()
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='DISPONIBLE')
    imagen = models.ImageField(upload_to='habitaciones/', blank=True, null=True)
    

    descripcion = models.TextField(blank=True, null=True, default="Espacio confortable dotado de excelente iluminación y amenidades completas.")
    modalidad = models.CharField(max_length=10, choices=MODALIDAD_CHOICES, default='NOCHE')

    def __str__(self):
        return f"Habitación {self.numero} - {self.tipo_habitacion.nombre}"

class Huesped(models.Model):
    TIPOS_DOCUMENTO = [
        ('CC', 'Cédula de Ciudadanía'),
        ('CE', 'Cédula de Extranjería'),
        ('TI', 'Tarjeta de Identidad'),
        ('RC', 'Registro Civil'),
    ]
    tipo_documento = models.CharField(max_length=2, choices=TIPOS_DOCUMENTO, default='CC')
    numero_documento = models.CharField(max_length=20, unique=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20)
    correo = models.EmailField(blank=True, null=True)
    nacionalidad = models.CharField(max_length=50, default='Colombiana')

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"

class Reserva(models.Model):
    ESTADOS_RESERVA = [
        ('PENDIENTE', 'Pendiente'),
        ('CONFIRMADA', 'Confirmada'),
        ('EN_ESTANCIA', 'En Estancia'),
        ('FINALIZADA', 'Finalizada'),
        ('CANCELADA', 'Cancelada'),
    ]
    METODOS_PAGO = [
        ('TRANSFERENCIA', 'Transferencia bancaria'),
        ('TARJETA', 'Tarjeta (coordinación con el hotel)'),
    ]
    huesped = models.ForeignKey(Huesped, on_delete=models.CASCADE)
    habitacion = models.ForeignKey(Habitacion, on_delete=models.CASCADE)
    fecha_entrada = models.DateField()
    fecha_salida = models.DateField()
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, default='TRANSFERENCIA')
    monto_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=ESTADOS_RESERVA, default='PENDIENTE')
    creada_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reserva #{self.id} - {self.huesped.nombres}"

class Servicio(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.nombre} (${self.costo})"

class ServicioReserva(models.Model):
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='servicios_asociados')
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.servicio.nombre} (x{self.cantidad})"

class Pago(models.Model):
    METODOS_PAGO = [
        ('EFECTIVO', 'Efectivo'),
        ('TRANSFERENCIA', 'Transferencia Bancaria'),
        ('TARJETA', 'Tarjeta'),
    ]
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='pagos')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=20, choices=METODOS_PAGO)
    fecha_pago = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pago de ${self.monto} - Reserva #{self.reserva.id}"


class ComprobanteTransferencia(models.Model):
    ESTADOS = [
        ('PENDIENTE', 'Pendiente de revisión'),
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
    ]

    reserva = models.ForeignKey(
        Reserva,
        on_delete=models.CASCADE,
        related_name='comprobantes',
    )
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    archivo = models.BinaryField()
    nombre_archivo = models.CharField(max_length=255)
    tipo_archivo = models.CharField(max_length=50)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"Comprobante de reserva #{self.reserva_id} ({self.estado})"


class Galeria(models.Model):
    titulo = models.CharField(max_length=100, blank=True, null=True, verbose_name="Título")
    imagen = models.ImageField(upload_to='galeria/', verbose_name="Imagen")
    fecha_subida = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titulo if self.titulo else f"Imagen {self.id}"

    