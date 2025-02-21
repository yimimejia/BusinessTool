<?php
require_once 'conexion.php';
require_once 'includes/auth.php';
checkLogin();

if (!isAdmin()) {
    header('Location: edit.php');
    exit();
}

// Gestión de diseñadores
if ($_SERVER['REQUEST_METHOD'] == 'POST') {
    if (isset($_POST['action'])) {
        switch ($_POST['action']) {
            case 'add_designer':
                $nombre = sanitize($_POST['nombre']);
                $usuario = sanitize($_POST['usuario']);
                $password = password_hash($_POST['password'], PASSWORD_DEFAULT);
                
                $stmt = $pdo->prepare("INSERT INTO diseñadores (nombre, usuario, password, es_admin) VALUES (?, ?, ?, 0)");
                $stmt->execute([$nombre, $usuario, $password]);
                $mensaje = "Diseñador agregado exitosamente";
                break;
                
            case 'delete_designer':
                $id = sanitize($_POST['designer_id']);
                $stmt = $pdo->prepare("DELETE FROM diseñadores WHERE id = ? AND es_admin = 0");
                $stmt->execute([$id]);
                $mensaje = "Diseñador eliminado exitosamente";
                break;
        }
    }
}

// Obtener lista de diseñadores
$stmt = $pdo->query("SELECT * FROM diseñadores WHERE es_admin = 0");
$diseñadores = $stmt->fetchAll();

include 'includes/header.php';
?>

<?php if (isset($mensaje)): ?>
    <div class="alert alert-success"><?php echo $mensaje; ?></div>
<?php endif; ?>

<div class="row">
    <div class="col-md-6">
        <div class="card mb-4">
            <div class="card-header">
                <h4>Agregar Nuevo Diseñador</h4>
            </div>
            <div class="card-body">
                <form method="POST">
                    <input type="hidden" name="action" value="add_designer">
                    <div class="mb-3">
                        <label class="form-label">Nombre:</label>
                        <input type="text" name="nombre" class="form-control" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Usuario:</label>
                        <input type="text" name="usuario" class="form-control" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Contraseña:</label>
                        <input type="password" name="password" class="form-control" required>
                    </div>
                    <button type="submit" class="btn btn-primary">Agregar Diseñador</button>
                </form>
            </div>
        </div>
    </div>
    
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h4>Diseñadores Actuales</h4>
            </div>
            <div class="card-body">
                <table class="table">
                    <thead>
                        <tr>
                            <th>Nombre</th>
                            <th>Usuario</th>
                            <th>Acciones</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($diseñadores as $diseñador): ?>
                        <tr>
                            <td><?php echo $diseñador['nombre']; ?></td>
                            <td><?php echo $diseñador['usuario']; ?></td>
                            <td>
                                <form method="POST" style="display: inline;">
                                    <input type="hidden" name="action" value="delete_designer">
                                    <input type="hidden" name="designer_id" value="<?php echo $diseñador['id']; ?>">
                                    <button type="submit" class="btn btn-danger btn-sm" 
                                            onclick="return confirm('¿Eliminar este diseñador?')">
                                        Eliminar
                                    </button>
                                </form>
                            </td>
                        </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<?php include 'includes/footer.php'; ?>
