<?php
require_once 'conexion.php';
require_once 'includes/auth.php';
checkLogin();

if (!isServicio()) {
    header('Location: edit.php');
    exit();
}

// Obtener todos los trabajos pendientes
$stmt = $pdo->query("SELECT d.*, dis.nombre as nombre_diseñador 
                     FROM datos d 
                     LEFT JOIN diseñadores dis ON d.diseñador_id = dis.id 
                     ORDER BY d.fecha DESC");
$trabajos = $stmt->fetchAll();

include 'includes/header.php';
?>

<div class="card">
    <div class="card-header">
        <h4>Supervisión de Trabajos</h4>
    </div>
    <div class="card-body">
        <table class="table table-striped" id="servicioTable">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Descripción</th>
                    <th>Diseñador</th>
                    <th>Factura</th>
                    <th>Cliente</th>
                    <th>Fecha</th>
                    <th>Teléfono</th>
                    <th>Estado</th>
                </tr>
            </thead>
            <tbody>
                <?php foreach ($trabajos as $trabajo): ?>
                <tr>
                    <td><?php echo $trabajo['id']; ?></td>
                    <td><?php echo $trabajo['descripcion']; ?></td>
                    <td><?php echo $trabajo['nombre_diseñador']; ?></td>
                    <td><?php echo $trabajo['no_factura']; ?></td>
                    <td><?php echo $trabajo['cliente']; ?></td>
                    <td><?php echo $trabajo['fecha']; ?></td>
                    <td><?php echo $trabajo['numero_de_telefono']; ?></td>
                    <td>
                        <span class="badge bg-warning">Pendiente</span>
                    </td>
                </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</div>

<script>
$(document).ready(function() {
    $('#servicioTable').DataTable({
        language: {
            url: '//cdn.datatables.net/plug-ins/1.13.7/i18n/es-ES.json'
        },
        order: [[5, 'desc']]
    });
});
</script>

<?php include 'includes/footer.php'; ?>
