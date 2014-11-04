var ticTacToeApp = angular.module('ticTacToeApp', []);

ticTacToeApp.config(function($interpolateProvider) {
  "use strict";

  $interpolateProvider.startSymbol('{$');
  $interpolateProvider.endSymbol('$}');
});

var ticTacToeCtrl = ticTacToeApp.controller('ticTacToeCtrl', function($scope, $q, $http, $timeout) {
  "use strict";

  var parseResponse = function(respData) {
    $scope.cells = respData.cells;
    $scope.gameStatus = respData.status;
  };

  $scope.getLatestGame = function() {
    $http.get('latest_game').success(parseResponse);
  };

  $scope.getLatestGame();

  $scope.cells = [
    [null, null, null],
    [null, null, null],
    [null, null, null]
  ];

  $scope.gameStatus = null;

  $scope.getClassForCell = function(x, y) {
    "use strict";

    var emptyStyle = "fa fa-4x col-md-3";
    var cellVal = $scope.cells[x][y];

    if(cellVal === null) {
      return emptyStyle + " fa-square-o invisible";
    } else if(cellVal === 'x') {
      return emptyStyle + " fa-close red";
    } else if(cellVal === 'o') {
      return emptyStyle + " fa-circle-o red";
    }
  };

  $scope.cellClicked = function(x, y) {
    "use strict";

    if($scope.cells[x][y] !== null) { // there is already a move at this location
      return;
    } else if ($scope.gameStatus === 'won' || $scope.gameStatus === 'tie') {
      return;
    }

    $scope.cells[x][y] = 'x';
    $scope.showSpinner = true;
    $('#myModal').modal('show');
    $http.post('cell_click', angular.toJson({x: x, y: y}))
      .success(parseResponse)
      .error(function(respData) {
        angular.noop();
      }).then(function() {
        $scope.showSpinner = false
        $('#myModal').modal('hide');
      });
  };

  $scope.newGame = function() {
    $http.post('new_game').success(parseResponse);
  }
});