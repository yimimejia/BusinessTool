<?php
require_once 'conexion.php';
require_once 'includes/auth.php';
checkLogin();

// Marcar trabajo como listo
if (isset($_GET['marcar_listo'])) {
    $id = sanitize($_GET['marcar_listo']);
    
    // Obtener datos del trabajo
    $stmt = $pdo->prepare("SELECT * FROM datos WHERE id = ?");
    $stmt->execute([$id]);
    $trabajo = $stmt->fetch();
    
    if ($trabajo) {
        // Insertar en tabla listos
        $stmt = $pdo->prepare("INSERT INTO listos (descripcion, diseñador, no_factura, cliente, fecha, numero_de_telefono) 
                              VALUES (?, ?, ?, ?, CURDATE(), ?)");
        $stmt->execute([
            $trabajo['descripcion'],
            $trabajo['diseñador'],
            $trabajo['no_factura'],
            $trabajo['cliente'],
            $trabajo['numero_de_telefono']
        ]);
        
        // Eliminar de datos
        $stmt = $pdo->prepare("DELETE FROM datos WHERE id = ?");
        $stmt->execute([$id]);
        
        $mensaje = "Trabajo marcado como listo exitosamente";
    }
}

// Obtener trabajos listos
$stmt = $pdo->query("SELECT * FROM listos ORDER BY fecha DESC");
$trabajos_listos = $stmt->fetchAll();

include 'includes/header.php';
?>

<?php if (isset($mensaje)): ?>
    <div class="alert alert-success"><?php echo $mensaje; ?></div>
<?php endif; ?>

<div class="card">
    <div class="card-header">
        <h4>Trabajos Completados</h4>
    </div>
    <div class="card-body">
        <table class="table table-striped" id="trabajosListosTable">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Descripción</th>
                    <th>Diseñador</th>
                    <th>Factura</th>
                    <th>Cliente</th>
                    <th>Fecha</th>
                    <th>Teléfono</th>
                </tr>
            </thead>
            <tbody>
                <?php foreach ($trabajos_listos as $trabajo): ?>
                <tr>
                    <td><?php echo $trabajo['id']; ?></td>
                    <td><?php echo $trabajo['descripcion']; ?></td>
                    <td><?php echo $trabajo['diseñador']; ?></td>
                    <td><?php echo $trabajo['no_factura']; ?></td>
                    <td><?php echo $trabajo['cliente']; ?></td>
                    <td><?php echo $trabajo['fecha']; ?></td>
                    <td><?php echo $trabajo['numero_de_telefono']; ?></td>
                </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</div>

<script>
$(document).ready(function() {
    $('#trabajosListosTable').DataTable({
        language: {
            url: '//cdn.datatables.net/plug-ins/1.13.7/i18n/es-ES.json'
        },
        order: [[5, 'desc']]
    });
});
</script>

<?php include 'includes/footer.php'; ?>
