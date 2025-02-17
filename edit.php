<?php
require_once 'conexion.php';
require_once 'includes/auth.php';
checkLogin();

if ($_SERVER['REQUEST_METHOD'] == 'POST') {
    $descripcion = sanitize($_POST['descripcion']);
    $diseñador_id = sanitize($_POST['diseñador_id']);
    $no_factura = sanitize($_POST['no_factura']);
    $cliente = sanitize($_POST['cliente']);
    $telefono = sanitize($_POST['telefono']);

    $stmt = $pdo->prepare("INSERT INTO datos (descripcion, diseñador_id, no_factura, cliente, fecha, numero_de_telefono) 
                          VALUES (?, ?, ?, ?, CURDATE(), ?)");
    $stmt->execute([$descripcion, $diseñador_id, $no_factura, $cliente, $telefono]);
    
    $mensaje = "Trabajo registrado exitosamente";
}

// Obtener lista de diseñadores
$stmt = $pdo->query("SELECT * FROM diseñadores WHERE es_admin = 0");
$diseñadores = $stmt->fetchAll();

// Obtener trabajos pendientes
$query = "SELECT d.*, dis.nombre as nombre_diseñador 
          FROM datos d 
          LEFT JOIN diseñadores dis ON d.diseñador_id = dis.id";
if (!isAdmin()) {
    $query .= " WHERE d.diseñador_id = ?";
}
$stmt = $pdo->prepare($query);
if (!isAdmin()) {
    $stmt->execute([getUserId()]);
} else {
    $stmt->execute();
}
$trabajos = $stmt->fetchAll();

include 'includes/header.php';
?>

<?php if (isset($mensaje)): ?>
    <div class="alert alert-success"><?php echo $mensaje; ?></div>
<?php endif; ?>

<?php if (isAdmin()): ?>
<div class="card mb-4">
    <div class="card-header">
        <h4>Registrar Nuevo Trabajo</h4>
    </div>
    <div class="card-body">
        <form method="POST">
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Descripción:</label>
                    <textarea name="descripcion" class="form-control" required></textarea>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Diseñador:</label>
                    <select name="diseñador_id" class="form-control" required>
                        <?php foreach ($diseñadores as $diseñador): ?>
                            <option value="<?php echo $diseñador['id']; ?>">
                                <?php echo $diseñador['nombre']; ?>
                            </option>
                        <?php endforeach; ?>
                    </select>
                </div>
                <div class="col-md-4 mb-3">
                    <label class="form-label">No. Factura:</label>
                    <input type="text" name="no_factura" class="form-control" required>
                </div>
                <div class="col-md-4 mb-3">
                    <label class="form-label">Cliente:</label>
                    <input type="text" name="cliente" class="form-control" required>
                </div>
                <div class="col-md-4 mb-3">
                    <label class="form-label">Teléfono:</label>
                    <input type="text" name="telefono" class="form-control" required>
                </div>
            </div>
            <button type="submit" class="btn btn-primary">Registrar Trabajo</button>
        </form>
    </div>
</div>
<?php endif; ?>

<div class="card">
    <div class="card-header">
        <h4>Trabajos Pendientes</h4>
    </div>
    <div class="card-body">
        <table class="table table-striped" id="trabajosTable">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Descripción</th>
                    <th>Diseñador</th>
                    <th>Factura</th>
                    <th>Cliente</th>
                    <th>Fecha</th>
                    <th>Teléfono</th>
                    <th>Acciones</th>
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
                        <button class="btn btn-success btn-sm marcar-listo" 
                                data-id="<?php echo $trabajo['id']; ?>">
                            Marcar Listo
                        </button>
                    </td>
                </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</div>

<script>
$(document).ready(function() {
    $('#trabajosTable').DataTable({
        language: {
            url: '//cdn.datatables.net/plug-ins/1.13.7/i18n/es-ES.json'
        }
    });

    $('.marcar-listo').click(function() {
        if (confirm('¿Marcar este trabajo como listo?')) {
            const id = $(this).data('id');
            window.location.href = 'trabajos_listos.php?marcar_listo=' + id;
        }
    });
});
</script>

<?php include 'includes/footer.php'; ?>
