<?php
    header("Content-Type: text/plain");
    echo "User IP: ${_SERVER['REMOTE_ADDR']}, Host Server Name: ${_SERVER['SERVER_NAME']} - Hello, world!\n";
?>